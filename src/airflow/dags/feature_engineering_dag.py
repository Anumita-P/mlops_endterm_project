"""
Airflow DAG: Feature Engineering Pipeline
Creates ML-ready features from training data with risk labels and engineered features.
Runs AFTER data_merge_pipeline completes.
FIXED: Handles inf/NaN before scaling
"""

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
import json
import logging
import traceback

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PROCESSED_DIR = Path("/home/airflow/data/processed")
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def engineer_features():
    """
    Feature engineering: Create risk labels, lagged features, interactions.
    Transforms training_dataset.csv into features_dataset.csv with ML-ready features.
    """
    logger.info("\n" + "=" * 80)
    logger.info("FEATURE ENGINEERING PIPELINE - STARTED")
    logger.info("=" * 80)
    
    try:
        # ============================================================
        # STEP 1: Load Training Data
        # ============================================================
        logger.info("\n[1/7] Loading Training Dataset...")
        
        training_file = DATA_PROCESSED_DIR / "training_dataset.csv"
        
        if not training_file.exists():
            raise FileNotFoundError(f"Training file not found: {training_file}")
        
        df = pd.read_csv(training_file)
        logger.info(f"  ✓ Loaded {len(df):,} records")
        logger.info(f"  ✓ Original columns: {len(df.columns)}")
        
        original_shape = df.shape
        
        # ============================================================
        # STEP 2: Create Yield Risk Label (Target Variable)
        # ============================================================
        logger.info("\n[2/7] Creating Yield Risk Labels...")
        
        # Calculate district-crop historical mean and std
        district_crop_stats = df.groupby(['district', 'crop'])['yield_kg_per_ha'].agg(['mean', 'std']).reset_index()
        district_crop_stats.columns = ['district', 'crop', 'hist_mean_yield', 'hist_std_yield']
        
        # Merge historical stats back to main dataset
        df = pd.merge(df, district_crop_stats, on=['district', 'crop'], how='left')
        
        # Calculate yield deviation from historical mean
        df['yield_deviation'] = df['yield_kg_per_ha'] - df['hist_mean_yield']
        df['yield_deviation_std'] = df['yield_deviation'] / (df['hist_std_yield'] + 1e-6)
        
        # Create binary risk label
        df['yield_risk_label'] = (df['yield_deviation_std'] < -1.0).astype(int)
        
        high_risk = (df['yield_risk_label'] == 1).sum()
        low_risk = (df['yield_risk_label'] == 0).sum()
        
        logger.info(f"  ✓ Created binary risk label")
        logger.info(f"    - HIGH RISK (1): {high_risk:,} ({high_risk/len(df)*100:.1f}%)")
        logger.info(f"    - LOW RISK (0): {low_risk:,} ({low_risk/len(df)*100:.1f}%)")
        
        # ============================================================
        # STEP 3: Create Lagged Features (Time-Series)
        # ============================================================
        logger.info("\n[3/7] Creating Lagged Features...")
        
        # Sort by district, crop, year
        df = df.sort_values(['district', 'crop', 'year']).reset_index(drop=True)
        
        # Lag features
        df['lag1_yield_kg_per_ha'] = df.groupby(['district', 'crop'])['yield_kg_per_ha'].shift(1)
        df['lag2_yield_kg_per_ha'] = df.groupby(['district', 'crop'])['yield_kg_per_ha'].shift(2)
        df['yield_change_pct'] = df.groupby(['district', 'crop'])['yield_kg_per_ha'].pct_change() * 100
        
        logger.info(f"  ✓ Created 3 lagged features")
        
        # ============================================================
        # STEP 4: Create Interaction & Ratio Features
        # ============================================================
        logger.info("\n[4/7] Creating Interaction Features...")
        
        # Rainfall to irrigation water requirement ratio
        df['rainfall_to_water_ratio'] = df['rainfall_mm_sum'] / (df['water_requirement_mm'] + 1)
        
        # Temperature range
        df['temp_range'] = df['temp_mean_c_max'] - df['temp_mean_c_min']
        
        # Rainfall adequacy
        df['rainfall_adequacy'] = df['rainfall_mm_sum'] / (df['water_requirement_mm'] + 1)
        
        # Heat stress indicator
        df['heat_stress_index'] = (df['temp_max_c_mean'] * df['humidity_percent_mean']) / 100
        
        # Economic efficiency ratio
        df['yield_to_msp_ratio'] = df['yield_kg_per_ha'] / (df['msp_per_quintal'] * 10 + 1)
        
        logger.info(f"  ✓ Created 5 interaction features")
        
        # ============================================================
        # STEP 5: Clean Data (Replace inf/NaN BEFORE scaling)
        # ============================================================
        logger.info("\n[5/7] Cleaning Data (Inf & NaN)...")
        
        missing_before = df.isnull().sum().sum()
        
        # Replace infinity with NaN
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # Define feature groups
        lagged_features = ['lag1_yield_kg_per_ha', 'lag2_yield_kg_per_ha', 'yield_change_pct']
        
        # Forward fill lagged features within groups
        for col in lagged_features:
            if col in df.columns:
                df[col] = df.groupby(['district', 'crop'])[col].bfill()
        
        # Fill with crop group mean
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            if df[col].isnull().any():
                group_mean = df.groupby('crop')[col].transform('mean')
                df[col].fillna(group_mean, inplace=True)
        
        # Fill remaining with global mean
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            if df[col].isnull().any():
                df[col].fillna(df[col].mean(), inplace=True)
        
        # Replace any remaining inf with median
        df = df.replace([np.inf, -np.inf], np.nan)
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            if df[col].isnull().any():
                df[col].fillna(df[col].median(), inplace=True)
        
        missing_after = df.isnull().sum().sum()
        
        logger.info(f"  ✓ Missing values: {missing_before} → {missing_after}")
        
        # ============================================================
        # STEP 6: Scale Numerical Features
        # ============================================================
        logger.info("\n[6/7] Scaling Numerical Features...")
        
        # Identify feature groups
        weather_features = [col for col in df.columns 
                          if any(x in col for x in ['temp', 'rainfall', 'humidity', 'wind'])]
        
        interaction_features = [
            'rainfall_to_water_ratio', 'temp_range', 'rainfall_adequacy',
            'heat_stress_index', 'yield_to_msp_ratio'
        ]
        
        reference_features = ['msp_per_quintal', 'water_requirement_mm']
        
        # All features to scale
        all_scaling_features = weather_features + interaction_features + lagged_features + reference_features
        scaling_features = [f for f in all_scaling_features if f in df.columns]
        
        # Scale
        scaler = RobustScaler()
        df_for_scaling = df[scaling_features].copy()
        df_scaled_values = scaler.fit_transform(df_for_scaling)
        
        # Add scaled columns
        for i, col in enumerate(scaling_features):
            df[f'{col}_scaled'] = df_scaled_values[:, i]
        
        scaled_cols = [c for c in df.columns if '_scaled' in c]
        
        logger.info(f"  ✓ Scaled {len(scaling_features)} features")
        logger.info(f"  ✓ Added {len(scaled_cols)} scaled columns")
        
        # ============================================================
        # STEP 7: Save Features Dataset
        # ============================================================
        logger.info("\n[7/7] Saving Features Dataset...")
        
        output_file = DATA_PROCESSED_DIR / "features_dataset.csv"
        df.to_csv(output_file, index=False)
        
        file_size_mb = output_file.stat().st_size / 1024 / 1024
        
        logger.info(f"  ✓ Saved: {output_file}")
        logger.info(f"  ✓ Records: {len(df):,}")
        logger.info(f"  ✓ Features: {len(df.columns)} (new: {len(df.columns) - original_shape[1]})")
        logger.info(f"  ✓ File size: {file_size_mb:.2f} MB")
        
        # Generate report
        feature_report = {
            'pipeline_info': {
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            },
            'dataset_summary': {
                'records': int(len(df)),
                'features': int(len(df.columns)),
                'new_features': int(len(df.columns) - original_shape[1])
            },
            'target_variable': {
                'name': 'yield_risk_label',
                'high_risk': int(high_risk),
                'low_risk': int(low_risk),
                'high_risk_pct': float(high_risk / len(df) * 100)
            },
            'feature_engineering': {
                'weather_features': int(len(weather_features)),
                'interaction_features': int(len(interaction_features)),
                'lagged_features': int(len(lagged_features)),
                'scaled_features': int(len(scaled_cols))
            }
        }
        
        report_file = DATA_PROCESSED_DIR / "feature_engineering_report.json"
        with open(report_file, 'w') as f:
            json.dump(feature_report, f, indent=2)
        
        logger.info(f"  ✓ Report saved")
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        logger.info("\n" + "=" * 80)
        logger.info("✓ FEATURE ENGINEERING PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"  Records: {len(df):,}")
        logger.info(f"  Features: {len(df.columns)}")
        logger.info(f"  New Features: {len(df.columns) - original_shape[1]}")
        logger.info(f"  Target (yield_risk_label):")
        logger.info(f"    - HIGH RISK: {high_risk:,} ({high_risk/len(df)*100:.1f}%)")
        logger.info(f"    - LOW RISK: {low_risk:,} ({low_risk/len(df)*100:.1f}%)")
        logger.info("=" * 80 + "\n")
        
        return {
            'status': 'success',
            'records': len(df),
            'features': len(df.columns),
            'high_risk_count': high_risk
        }
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ERROR IN FEATURE ENGINEERING PIPELINE")
        logger.error("=" * 80)
        logger.error(f"Exception: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80 + "\n")
        raise


# ============================================================
# AIRFLOW DAG
# ============================================================

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'feature_engineering_pipeline',
    default_args=default_args,
    description='Feature Engineering: Risk labels, lagged & interaction features',
    schedule_interval='@weekly',
    catchup=False,
    tags=['feature-engineering', 'ml-preparation']
)

start_task = DummyOperator(task_id='start', dag=dag)

engineer_task = PythonOperator(
    task_id='engineer_features',
    python_callable=engineer_features,
    dag=dag,
    provide_context=True
)

end_task = DummyOperator(task_id='end', dag=dag)

start_task >> engineer_task >> end_task