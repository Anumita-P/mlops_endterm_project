"""
Airflow DAG: MLflow Model Tracking
Logs yield risk model metrics to MLflow for experiment tracking.
Simplified: metrics & params only (no artifacts to avoid path issues)
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

import mlflow

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_MODELS_DIR = Path("/home/airflow/data/models")


def log_model_to_mlflow():
    """Log trained model metrics to MLflow."""
    logger.info("\n" + "=" * 80)
    logger.info("MLFLOW MODEL TRACKING")
    logger.info("=" * 80)
    
    try:
        # Set MLflow tracking URI
        mlflow.set_tracking_uri("http://host.docker.internal:5000")
        mlflow.set_experiment("yield_risk_prediction")
        
        logger.info(f"\n[1/2] Loading Metrics...")
        
        # Load metrics
        metrics_file = DATA_MODELS_DIR / "model_metrics.json"
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        logger.info(f"  ✓ Loaded metrics")
        
        # Load config
        config_file = DATA_MODELS_DIR / "model_config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"  ✓ Loaded config")
        
        # Start MLflow run
        logger.info(f"\n[2/2] Logging to MLflow...")
        
        with mlflow.start_run(run_name="yield_risk_rf_v1"):
            
            # Log parameters
            mlflow.log_param("model_type", "RandomForestClassifier")
            mlflow.log_param("n_estimators", 100)
            mlflow.log_param("max_depth", 15)
            mlflow.log_param("min_samples_split", 5)
            mlflow.log_param("class_weight", "balanced")
            mlflow.log_param("n_features", config['n_features'])
            
            # Log metrics
            mlflow.log_metric("train_accuracy", metrics['train_accuracy'])
            mlflow.log_metric("test_accuracy", metrics['test_accuracy'])
            mlflow.log_metric("test_precision", metrics['test_precision'])
            mlflow.log_metric("test_recall", metrics['test_recall'])
            mlflow.log_metric("test_f1_score", metrics['test_f1_score'])
            mlflow.log_metric("test_roc_auc", metrics['test_roc_auc'])
            mlflow.log_metric("train_records", metrics['train_records'])
            mlflow.log_metric("test_records", metrics['test_records'])
            
            # Log confusion matrix
            cm = metrics['confusion_matrix']
            mlflow.log_metric("tp", cm['true_positives'])
            mlflow.log_metric("fp", cm['false_positives'])
            mlflow.log_metric("fn", cm['false_negatives'])
            mlflow.log_metric("tn", cm['true_negatives'])
            
            # Tags
            mlflow.set_tag("pipeline", "yield_risk_prediction")
            mlflow.set_tag("crop", "rice_sugarcane")
            mlflow.set_tag("region", "tamil_nadu")
            mlflow.set_tag("version", "v1")
            
            logger.info(f"  ✓ Metrics logged!")
        
        # Summary
        logger.info(f"\n" + "=" * 80)
        logger.info("✓ MLFLOW TRACKING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n📊 EXPERIMENT: yield_risk_prediction")
        logger.info(f"  Run: yield_risk_rf_v1")
        logger.info(f"  Model: RandomForestClassifier")
        logger.info(f"\n📈 METRICS LOGGED:")
        logger.info(f"  Test Accuracy: {metrics['test_accuracy']:.4f}")
        logger.info(f"  Test F1-Score: {metrics['test_f1_score']:.4f}")
        logger.info(f"  Test ROC-AUC: {metrics['test_roc_auc']:.4f}")
        logger.info(f"\n🔗 VIEW AT: http://localhost:5000")
        logger.info("=" * 80 + "\n")
        
        return {'status': 'success'}
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ERROR")
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
    'mlflow_model_tracking',
    default_args=default_args,
    description='Log model metrics to MLflow for experiment tracking',
    schedule_interval=None,
    catchup=False,
    tags=['mlflow', 'model-tracking', 'mlops']
)

start = DummyOperator(task_id='start', dag=dag)
track = PythonOperator(task_id='log_model_to_mlflow', python_callable=log_model_to_mlflow, dag=dag)
end = DummyOperator(task_id='end', dag=dag)

start >> track >> end