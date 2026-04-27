"""
Airflow DAG: Data Merge Pipeline
Merges weather, yield, and reference data into a training dataset.
"""

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import json
import logging
import traceback

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATA_RAW_DIR = Path("/home/airflow/data/raw")
DATA_PROCESSED_DIR = Path("/home/airflow/data/processed")
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


dag = DAG(
    'data_merge_pipeline',
    default_args=default_args,
    description='Merge weather, yield, and reference data for ML training',
    schedule_interval='@weekly',
    catchup=False,
    tags=['data-preparation', 'mlops']
)


def merge_and_process_data():
    """Complete data merge and processing pipeline."""
    logger.info("\n" + "=" * 80)
    logger.info("MLOPS DATA MERGE PIPELINE - STARTED")
    logger.info("=" * 80)

    try:
        # STEP 1: Load and Validate Weather Data
        logger.info("\n[1/6] Loading Weather Data (NASA POWER)...")

        weather_file = DATA_RAW_DIR / "weather" / "nasa_power_tn.csv"
        if not weather_file.exists():
            raise FileNotFoundError(f"Weather file not found: {weather_file}")

        df_weather = pd.read_csv(weather_file)
        logger.info(f"  ✓ Loaded {len(df_weather):,} daily weather records")
        logger.info(f"  Columns: {list(df_weather.columns)}")
        logger.info(f"  Date range: {df_weather['date'].min()} to {df_weather['date'].max()}")
        logger.info(f"  Unique districts: {df_weather['district'].nunique()}")

        # Standardize column names
        df_weather.rename(columns={
            'T2M': 'temp_mean_c',
            'T2M_MAX': 'temp_max_c',
            'T2M_MIN': 'temp_min_c',
            'PRECTOTCORR': 'rainfall_mm',
            'RH2M': 'humidity_percent',
            'WS10M': 'wind_speed_ms'
        }, inplace=True)

        df_weather['date'] = pd.to_datetime(df_weather['date'])
        df_weather['year'] = df_weather['date'].dt.year
        df_weather['month'] = df_weather['date'].dt.month

        logger.info(f"  ✓ Weather data validated and standardized")

        # STEP 2: Load and Validate Crop Yield Data
        logger.info("\n[2/6] Loading Crop Yield Data...")

        yield_file = DATA_RAW_DIR / "crop_yield" / "India Agriculture Crop Production.csv"
        if not yield_file.exists():
            raise FileNotFoundError(f"Yield file not found: {yield_file}")

        df_yield = pd.read_csv(yield_file)
        logger.info(f"  ✓ Loaded {len(df_yield):,} total crop records")

        # Filter for Tamil Nadu
        df_yield_tn = df_yield[df_yield['State'] == 'Tamil Nadu'].copy()
        logger.info(f"  Filtered to {len(df_yield_tn):,} Tamil Nadu records")

        # Filter for Rice and Sugarcane
        df_yield_target = df_yield_tn[df_yield_tn['Crop'].isin(['Rice', 'Sugarcane'])].copy()
        logger.info(f"  Filtered to {len(df_yield_target):,} Rice + Sugarcane records")

        # Standardize column names
        df_yield_target = df_yield_target.rename(columns={
            'District': 'district',
            'Year': 'year',
            'Crop': 'crop',
            'Yield': 'yield_kg_per_ha'
        })

        # Convert financial‑year string (e.g., '2001-02') to int year (first year)
        df_yield_target['year'] = (
            df_yield_target['year']
            .astype(str)
            .str.split('-', expand=True)
            [0]               # first part: e.g., '2001'
            .astype(int)
        )

        # Remove records with missing yield
        df_yield_target = df_yield_target.dropna(subset=['yield_kg_per_ha'])

        logger.info(f"  ✓ Yield data validated ({len(df_yield_target):,} records)")
        logger.info(f"  Crops: {df_yield_target['crop'].unique().tolist()}")
        logger.info(f"  Year range: {df_yield_target['year'].min()}-{df_yield_target['year'].max()}")

        # STEP 3: Aggregate Daily Weather to Yearly Features
        logger.info("\n[3/6] Aggregating Daily Weather to Yearly Features...")

        weather_agg = df_weather.groupby(['district', 'year']).agg({
            'temp_mean_c': ['mean', 'min', 'max'],
            'temp_max_c': ['mean', 'max'],
            'temp_min_c': ['mean', 'min'],
            'rainfall_mm': ['sum', 'mean'],
            'humidity_percent': ['mean', 'min', 'max'],
            'wind_speed_ms': ['mean', 'max']
        }).reset_index()

        # Flatten multi-level column names
        weather_agg.columns = ['_'.join(col).strip('_') if col[1] else col[0]
                              for col in weather_agg.columns.values]

        logger.info(f"  ✓ Aggregated to {len(weather_agg):,} district-year records")
        logger.info(f"  Features: {len(weather_agg.columns) - 2} weather features")

        # STEP 4: Merge Weather with Yield Data
        logger.info("\n[4/6] Merging Weather and Yield Data...")

        # Standardize district names (handle case sensitivity)
        weather_agg['district'] = weather_agg['district'].str.title()
        df_yield_target['district'] = df_yield_target['district'].str.title()

        # Convert year to int for both dataframes
        weather_agg['year'] = weather_agg['year'].astype(int)
        df_yield_target['year'] = df_yield_target['year'].astype(int)

        # Aggregate yield by district-year
        df_yield_agg = df_yield_target.groupby(['district', 'year']).agg({
            'crop': 'first',
            'yield_kg_per_ha': 'mean'
        }).reset_index()

        # Merge on district and year
        df_training = pd.merge(
            weather_agg,
            df_yield_agg,
            on=['district', 'year'],
            how='inner'
        )

        if len(df_training) == 0:
            logger.warning("No matches found after merge!")
            logger.info(f"Weather districts: {weather_agg['district'].unique()[:5]}")
            logger.info(f"Yield districts: {df_yield_agg['district'].unique()[:5]}")
            raise ValueError("No matching district-year combinations found!")

        logger.info(f"  ✓ Merged to {len(df_training):,} training records")
        logger.info(f"  Features: {len(df_training.columns)} total columns")

        # STEP 5: Add Reference Data (MSP, Schemes, Irrigation)
        logger.info("\n[5/6] Adding Reference Data...")

        # Load MSP data
        msp_file = DATA_RAW_DIR / "schemes_msp" / "msp_rice_sugarcane_2020_2024.csv"
        if msp_file.exists():
            df_msp = pd.read_csv(msp_file)
            # Normalize crop names
            df_msp['crop'] = df_msp['crop'].str.replace(' \(.*\)', '', regex=True).str.title()
            df_training = pd.merge(
                df_training,
                df_msp[['crop', 'year', 'msp_per_quintal']],
                on=['crop', 'year'],
                how='left'
            )
            logger.info(f"  ✓ Added MSP data")
        else:
            logger.warning(f"  ⚠️  MSP file not found: {msp_file}")

        # Load irrigation norms
        irrigation_file = DATA_RAW_DIR / "schemes_msp" / "irrigation_norms_tn.csv"
        if irrigation_file.exists():
            df_irrigation = pd.read_csv(irrigation_file)
            df_irrigation_crop = df_irrigation.groupby('crop').agg({
                'water_requirement_mm': 'first'
            }).reset_index()
            df_training = pd.merge(
                df_training,
                df_irrigation_crop,
                on='crop',
                how='left'
            )
            logger.info(f"  ✓ Added irrigation norms")
        else:
            logger.warning(f"  ⚠️  Irrigation file not found: {irrigation_file}")

        logger.info(f"  Final training dataset: {len(df_training):,} records, {len(df_training.columns)} features")

        # STEP 6: Save Training Dataset
        logger.info("\n[6/6] Saving Training Dataset...")

        output_file = DATA_PROCESSED_DIR / "training_dataset.csv"
        df_training.to_csv(output_file, index=False)
        logger.info(f"  ✓ Saved training dataset: {output_file}")
        logger.info(f"  Size: {len(df_training):,} rows × {len(df_training.columns)} columns")

        # STEP 7: Compute Drift Baselines
        logger.info("\n[7/7] Computing Drift Baseline Statistics...")

        weather_features = [col for col in df_training.columns
                            if any(x in col for x in ['temp', 'rainfall', 'humidity', 'wind'])]

        baselines = {}
        for feature in weather_features:
            if feature in df_training.columns and df_training[feature].dtype in ['float64', 'int64']:
                baselines[feature] = {
                    'mean': float(df_training[feature].mean()),
                    'std': float(df_training[feature].std()),
                    'min': float(df_training[feature].min()),
                    'max': float(df_training[feature].max()),
                    'median': float(df_training[feature].median()),
                    '25th_percentile': float(df_training[feature].quantile(0.25)),
                    '75th_percentile': float(df_training[feature].quantile(0.75)),
                }

        baseline_file = DATA_PROCESSED_DIR / "drift_baselines.json"
        with open(baseline_file, 'w') as f:
            json.dump(baselines, f, indent=2)

        logger.info(f"  ✓ Computed {len(baselines)} weather feature baselines")
        logger.info(f"  Saved to: {baseline_file}")

        # STEP 8: Generate Data Quality Report
        logger.info("\n[8/8] Generating Data Quality Report...")

        report = {
            'pipeline_run': {
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            },
            'dataset_summary': {
                'total_records': int(len(df_training)),
                'total_features': int(len(df_training.columns)),
                'unique_districts': int(df_training['district'].nunique()),
                'unique_crops': df_training['crop'].unique().tolist(),
                'year_range': f"{int(df_training['year'].min())}-{int(df_training['year'].max())}",
            },
            'data_completeness': {
                col: f"{(1 - df_training[col].isnull().sum() / len(df_training)) * 100:.1f}%"
                for col in df_training.columns
            },
            'yield_statistics': {
                'mean_kg_per_ha': f"{df_training['yield_kg_per_ha'].mean():.2f}",
                'std_kg_per_ha': f"{df_training['yield_kg_per_ha'].std():.2f}",
                'min_kg_per_ha': f"{df_training['yield_kg_per_ha'].min():.2f}",
                'max_kg_per_ha': f"{df_training['yield_kg_per_ha'].max():.2f}",
            },
            'feature_summary': {
                'weather_features': len(weather_features),
                'reference_features': 2  # MSP, irrigation
            },
            'output_files': {
                'training_dataset': str(output_file),
                'drift_baselines': str(baseline_file),
                'quality_report': str(DATA_PROCESSED_DIR / "data_quality_report.json")
            }
        }

        report_file = DATA_PROCESSED_DIR / "data_quality_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"  ✓ Generated quality report: {report_file}")

        # SUMMARY
        logger.info("\n" + "=" * 80)
        logger.info("✓ DATA MERGE PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"  Training records: {len(df_training):,}")
        logger.info(f"  Features: {len(df_training.columns)}")
        logger.info(f"  Districts: {df_training['district'].nunique()}")
        logger.info(f"  Year range: {int(df_training['year'].min())}-{int(df_training['year'].max())}")
        logger.info(f"  Crops: {', '.join(df_training['crop'].unique())}")
        logger.info(f"\n📁 OUTPUT FILES:")
        logger.info(f"  1. {output_file}")
        logger.info(f"  2. {baseline_file}")
        logger.info(f"  3. {report_file}")
        logger.info("=" * 80 + "\n")

        return {
            'status': 'success',
            'records': len(df_training),
            'features': len(df_training.columns),
            'districts': df_training['district'].nunique(),
        }

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error(f"✗ ERROR IN DATA MERGE PIPELINE")
        logger.error("=" * 80)
        logger.error(f"Exception: {str(e)}")
        logger.error("\nFull Traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 80 + "\n")
        raise


# DAG TASKS
start_task = DummyOperator(task_id='start', dag=dag)

merge_task = PythonOperator(
    task_id='merge_and_process_data',
    python_callable=merge_and_process_data,
    dag=dag,
    provide_context=True
)

end_task = DummyOperator(task_id='end', dag=dag)

# Task dependencies
start_task >> merge_task >> end_task