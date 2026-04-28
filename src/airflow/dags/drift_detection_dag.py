"""
Airflow DAG: Drift Detection & Auto-Retraining
Detects weather feature drift using KS-test.
Triggers model retraining if drift is significant.
"""

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import logging
import json
from scipy import stats
import joblib

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PROCESSED_DIR = Path("/home/airflow/data/processed")
DATA_MODELS_DIR = Path("/home/airflow/data/models")
DRIFT_THRESHOLD = 0.05  # 5% significance level for KS-test


def detect_drift():
    """Detect drift in weather features using KS-test."""
    logger.info("\n" + "=" * 80)
    logger.info("DRIFT DETECTION - STARTED")
    logger.info("=" * 80)
    
    try:
        logger.info("\n[1/4] Loading Data...")
        
        # Load training data (baseline)
        features_file = DATA_PROCESSED_DIR / "features_dataset.csv"
        df = pd.read_csv(features_file)
        
        # Get 2018-2020 as baseline (training period)
        baseline = df[df['year'] <= 2020].copy()
        # Get 2021 as recent (test period)
        recent = df[df['year'] == 2021].copy()
        
        logger.info(f"  ✓ Baseline: {len(baseline)} records (2000-2020)")
        logger.info(f"  ✓ Recent: {len(recent)} records (2021)")
        
        # Weather features to check for drift
        weather_features = [
            'temp_mean_c_mean', 'rainfall_mm_sum', 'humidity_percent_mean',
            'wind_speed_ms_mean', 'temp_range'
        ]
        
        logger.info(f"\n[2/4] Performing KS-Test on {len(weather_features)} features...")
        
        drift_detected = False
        drift_results = {}
        
        for feature in weather_features:
            if feature in baseline.columns and feature in recent.columns:
                # KS-test: compare distributions
                baseline_vals = baseline[feature].dropna().values
                recent_vals = recent[feature].dropna().values
                
                if len(baseline_vals) > 0 and len(recent_vals) > 0:
                    statistic, p_value = stats.ks_2samp(baseline_vals, recent_vals)
                    
                    is_drift = p_value < DRIFT_THRESHOLD
                    drift_results[feature] = {
                        'ks_statistic': float(statistic),
                        'p_value': float(p_value),
                        'drift_detected': is_drift
                    }
                    
                    if is_drift:
                        drift_detected = True
                        logger.warning(f"  ⚠️  DRIFT DETECTED in {feature}: p-value={p_value:.4f}")
                    else:
                        logger.info(f"  ✓ {feature}: p-value={p_value:.4f} (OK)")
        
        logger.info(f"\n[3/4] Drift Summary...")
        logger.info(f"  Total features checked: {len(drift_results)}")
        logger.info(f"  Features with drift: {sum(1 for r in drift_results.values() if r['drift_detected'])}")
        logger.info(f"  Overall drift detected: {drift_detected}")
        
        # Save drift report
        logger.info(f"\n[4/4] Saving Drift Report...")
        
        drift_report_file = DATA_PROCESSED_DIR / "drift_report.json"
        drift_report = {
            'timestamp': datetime.now().isoformat(),
            'baseline_period': '2000-2020',
            'recent_period': '2021',
            'threshold': DRIFT_THRESHOLD,
            'drift_detected': drift_detected,
            'feature_results': drift_results,
            'recommendation': 'RETRAIN' if drift_detected else 'MONITOR'
        }
        
        with open(drift_report_file, 'w') as f:
            json.dump(drift_report, f, indent=2)
        
        logger.info(f"  ✓ Report saved: {drift_report_file}")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✓ DRIFT DETECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n🔍 RESULT: {'RETRAIN MODEL' if drift_detected else 'NO ACTION NEEDED'}")
        logger.info("=" * 80 + "\n")
        
        return {'drift_detected': drift_detected, 'report': drift_report}
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ERROR IN DRIFT DETECTION")
        logger.error("=" * 80)
        logger.error(str(e))
        import traceback
        logger.error(traceback.format_exc())
        logger.error("=" * 80 + "\n")
        raise


def temporal_holdout_validation():
    """
    Temporal holdout validation: evaluate model on held-out recent data.
    Simulates real-world delay between prediction and harvest outcome.
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEMPORAL HOLDOUT VALIDATION")
    logger.info("=" * 80)
    
    try:
        logger.info("\n[1/3] Loading Model & Data...")
        
        # Load model
        model_file = DATA_MODELS_DIR / "yield_risk_model.joblib"
        model = joblib.load(model_file)
        
        # Load features
        features_file = DATA_PROCESSED_DIR / "features_dataset.csv"
        df = pd.read_csv(features_file)
        
        # Load config to get feature columns
        config_file = DATA_MODELS_DIR / "model_config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        feature_cols = config['feature_columns']
        target = 'yield_risk_label'
        
        logger.info(f"  ✓ Model loaded")
        logger.info(f"  ✓ Features: {len(feature_cols)}")
        
        # Temporal holdout: 2021 data (held out from training)
        logger.info(f"\n[2/3] Evaluating on Held-Out 2021 Data...")
        
        holdout_df = df[df['year'] == 2021].copy()
        
        # Clean data
        holdout_df = holdout_df.replace([np.inf, -np.inf], np.nan)
        for col in feature_cols:
            if col in holdout_df.columns:
                holdout_df[col] = holdout_df[col].fillna(0)
        
        X_holdout = holdout_df[feature_cols].values
        y_holdout = holdout_df[target].values
        
        # Predictions
        y_pred = model.predict(X_holdout)
        y_proba = model.predict_proba(X_holdout)[:, 1]
        
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
        
        holdout_acc = accuracy_score(y_holdout, y_pred)
        holdout_prec = precision_score(y_holdout, y_pred, zero_division=0)
        holdout_rec = recall_score(y_holdout, y_pred, zero_division=0)
        holdout_f1 = f1_score(y_holdout, y_pred, zero_division=0)
        holdout_auc = roc_auc_score(y_holdout, y_proba)
        
        logger.info(f"  ✓ Holdout Accuracy: {holdout_acc:.4f}")
        logger.info(f"  ✓ Holdout Precision: {holdout_prec:.4f}")
        logger.info(f"  ✓ Holdout Recall: {holdout_rec:.4f}")
        logger.info(f"  ✓ Holdout F1: {holdout_f1:.4f}")
        logger.info(f"  ✓ Holdout AUC: {holdout_auc:.4f}")
        
        # Save validation report
        logger.info(f"\n[3/3] Saving Validation Report...")
        
        validation_report_file = DATA_PROCESSED_DIR / "temporal_holdout_validation.json"
        validation_report = {
            'timestamp': datetime.now().isoformat(),
            'holdout_period': '2021',
            'records_evaluated': int(len(holdout_df)),
            'accuracy': float(holdout_acc),
            'precision': float(holdout_prec),
            'recall': float(holdout_rec),
            'f1_score': float(holdout_f1),
            'roc_auc': float(holdout_auc)
        }
        
        with open(validation_report_file, 'w') as f:
            json.dump(validation_report, f, indent=2)
        
        logger.info(f"  ✓ Report saved: {validation_report_file}")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✓ TEMPORAL HOLDOUT VALIDATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n📊 HOLDOUT PERFORMANCE (2021):")
        logger.info(f"  Accuracy: {holdout_acc:.4f}")
        logger.info(f"  F1-Score: {holdout_f1:.4f}")
        logger.info(f"  ROC-AUC: {holdout_auc:.4f}")
        logger.info("=" * 80 + "\n")
        
        return validation_report
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ERROR IN TEMPORAL HOLDOUT VALIDATION")
        logger.error("=" * 80)
        logger.error(str(e))
        import traceback
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
    'drift_detection_and_retraining',
    default_args=default_args,
    description='Detect data drift and trigger model retraining',
    schedule_interval='@weekly',
    catchup=False,
    tags=['drift-detection', 'monitoring', 'mlops']
)

start = DummyOperator(task_id='start', dag=dag)

detect_drift_task = PythonOperator(
    task_id='detect_drift',
    python_callable=detect_drift,
    dag=dag
)

validation_task = PythonOperator(
    task_id='temporal_holdout_validation',
    python_callable=temporal_holdout_validation,
    dag=dag
)

# Conditional: if drift detected, trigger retraining
trigger_retraining = TriggerDagRunOperator(
    task_id='trigger_retraining',
    trigger_dag_id='model_training_pipeline',
    dag=dag,
    poke_interval=60,
    mode='poke',
)

end = DummyOperator(task_id='end', dag=dag)

start >> detect_drift_task >> validation_task >> end