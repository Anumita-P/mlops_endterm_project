"""
Airflow DAG: Model Training Pipeline
Trains Random Forest for yield risk prediction.
WORKING: Fill NaN with 0, exclude problematic columns
"""

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import json
import logging
import traceback
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PROCESSED_DIR = Path("/home/airflow/data/processed")
DATA_MODELS_DIR = Path("/home/airflow/data/models")
DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)


def train_model():
    """Train Random Forest for yield risk prediction."""
    logger.info("\n" + "=" * 80)
    logger.info("MODEL TRAINING PIPELINE")
    logger.info("=" * 80)
    
    try:
        # Load Features
        logger.info("\n[1/6] Loading Features...")
        
        features_file = DATA_PROCESSED_DIR / "features_dataset.csv"
        if not features_file.exists():
            raise FileNotFoundError(f"Features file not found: {features_file}")
        
        df = pd.read_csv(features_file)
        logger.info(f"  ✓ Loaded {len(df):,} records, {len(df.columns)} columns")
        
        # Train/Test Split
        logger.info("\n[2/6] Train/Test Split...")
        
        max_year = int(df['year'].max())
        test_year = max_year
        
        train_df = df[df['year'] < test_year].copy()
        test_df = df[df['year'] == test_year].copy()
        
        logger.info(f"  ✓ Train: {len(train_df):,} records ({int(train_df['year'].min())}-{int(train_df['year'].max())})")
        logger.info(f"  ✓ Test: {len(test_df):,} records")
        
        # Feature Selection
        logger.info("\n[3/6] Feature Selection...")
        
        target = 'yield_risk_label'
        
        # Exclude non-feature and all-NaN columns
        exclude_cols = {
            'district', 'year', 'crop',
            'yield_kg_per_ha', 'water_requirement_mm',
            'hist_mean_yield', 'hist_std_yield',
            'yield_deviation', 'yield_deviation_std',
            'msp_per_quintal',
            'yield_to_msp_ratio',
            'yield_to_msp_ratio_scaled',
            'msp_per_quintal_scaled'
        }
        
        feature_cols = [col for col in df.columns 
                       if col not in exclude_cols and col != target]
        
        logger.info(f"  ✓ Selected {len(feature_cols)} features")
        logger.info(f"  ✓ Excluded non-feature + all-NaN columns")
        
        # Data Cleaning
        logger.info("\n[4/6] Cleaning Data...")
        
        # Replace inf with NaN first
        train_df = train_df.replace([np.inf, -np.inf], np.nan)
        test_df = test_df.replace([np.inf, -np.inf], np.nan)
        
        # Fill all NaN with 0 (simple and effective)
        train_df[feature_cols] = train_df[feature_cols].fillna(0)
        test_df[feature_cols] = test_df[feature_cols].fillna(0)
        
        # Replace any remaining inf with 0
        train_df = train_df.replace([np.inf, -np.inf], 0)
        test_df = test_df.replace([np.inf, -np.inf], 0)
        
        logger.info(f"  ✓ Cleaned: train={len(train_df)}, test={len(test_df)}")
        
        # Prepare Data
        logger.info("\n[5/6] Preparing Training Data...")
        
        X_train = train_df[feature_cols].values
        y_train = train_df[target].values
        
        X_test = test_df[feature_cols].values
        y_test = test_df[target].values
        
        logger.info(f"  ✓ X_train: {X_train.shape}")
        logger.info(f"  ✓ X_test: {X_test.shape}")
        
        # Train Model
        logger.info("\n[6/6] Training Random Forest...")
        
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        
        rf_model.fit(X_train, y_train)
        logger.info(f"  ✓ Model trained")
        
        # Evaluate
        y_train_pred = rf_model.predict(X_train)
        y_test_pred = rf_model.predict(X_test)
        y_test_proba = rf_model.predict_proba(X_test)[:, 1]
        
        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        test_prec = precision_score(y_test, y_test_pred, zero_division=0)
        test_rec = recall_score(y_test, y_test_pred, zero_division=0)
        test_f1 = f1_score(y_test, y_test_pred, zero_division=0)
        test_auc = roc_auc_score(y_test, y_test_proba)
        
        tn, fp, fn, tp = confusion_matrix(y_test, y_test_pred).ravel()
        
        logger.info(f"  ✓ Train Accuracy: {train_acc:.4f}")
        logger.info(f"  ✓ Test Accuracy: {test_acc:.4f}")
        logger.info(f"  ✓ Test Precision: {test_prec:.4f}")
        logger.info(f"  ✓ Test Recall: {test_rec:.4f}")
        logger.info(f"  ✓ Test F1: {test_f1:.4f}")
        logger.info(f"  ✓ Test AUC: {test_auc:.4f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info(f"\n  Top 10 Features:")
        for idx, row in feature_importance.head(10).iterrows():
            logger.info(f"    {row['feature']}: {row['importance']:.4f}")
        
        # Save outputs
        logger.info(f"\n  Saving outputs...")
        
        # Model
        model_file = DATA_MODELS_DIR / "yield_risk_model.joblib"
        joblib.dump(rf_model, model_file)
        
        # Feature importance
        importance_file = DATA_MODELS_DIR / "feature_importance.csv"
        feature_importance.to_csv(importance_file, index=False)
        
        # Model config
        config_file = DATA_MODELS_DIR / "model_config.json"
        config = {
            'model_name': 'yield_risk_classifier',
            'model_type': 'RandomForestClassifier',
            'n_features': len(feature_cols),
            'feature_columns': feature_cols,
            'trained_date': datetime.now().isoformat()
        }
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Metrics
        metrics_file = DATA_MODELS_DIR / "model_metrics.json"
        metrics = {
            'model': 'yield_risk_classifier',
            'train_records': int(len(train_df)),
            'test_records': int(len(test_df)),
            'train_accuracy': float(train_acc),
            'test_accuracy': float(test_acc),
            'test_precision': float(test_prec),
            'test_recall': float(test_rec),
            'test_f1_score': float(test_f1),
            'test_roc_auc': float(test_auc),
            'confusion_matrix': {
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_positives': int(tp)
            },
            'top_10_features': feature_importance.head(10).to_dict('records'),
            'timestamp': datetime.now().isoformat()
        }
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"  ✓ All outputs saved to data/models/")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✓ MODEL TRAINING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n📊 FINAL PERFORMANCE:")
        logger.info(f"  Train Accuracy: {train_acc:.4f}")
        logger.info(f"  Test Accuracy: {test_acc:.4f}")
        logger.info(f"  Test Precision: {test_prec:.4f}")
        logger.info(f"  Test Recall: {test_rec:.4f}")
        logger.info(f"  Test F1-Score: {test_f1:.4f}")
        logger.info(f"  Test ROC-AUC: {test_auc:.4f}")
        logger.info(f"\n🎯 CONFUSION MATRIX:")
        logger.info(f"  TP: {tp}, FP: {fp}")
        logger.info(f"  FN: {fn}, TN: {tn}")
        logger.info(f"\n📁 SAVED FILES:")
        logger.info(f"  1. yield_risk_model.joblib")
        logger.info(f"  2. model_metrics.json")
        logger.info(f"  3. feature_importance.csv")
        logger.info(f"  4. model_config.json")
        logger.info("=" * 80 + "\n")
        
        return {
            'status': 'success',
            'test_accuracy': float(test_acc),
            'test_f1': float(test_f1),
            'test_auc': float(test_auc)
        }
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ERROR IN MODEL TRAINING")
        logger.error("=" * 80)
        logger.error(str(e))
        logger.error(traceback.format_exc())
        logger.error("=" * 80 + "\n")
        raise


# DAG
default_args = {
    'owner': 'data_scientist',
    'start_date': days_ago(1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'model_training_pipeline',
    default_args=default_args,
    description='Train Random Forest for yield risk prediction',
    schedule_interval='@weekly',
    catchup=False,
    tags=['model-training', 'ml', 'mlops']
)

start = DummyOperator(task_id='start', dag=dag)
train = PythonOperator(task_id='train_model', python_callable=train_model, dag=dag)
end = DummyOperator(task_id='end', dag=dag)

start >> train >> end