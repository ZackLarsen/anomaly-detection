# Python Packages and Tools

## Core data engineering

* **`pandas`** — Data manipulation, aggregation, joins
* **`polars`** — Faster dataframe operations for large datasets
* **`numpy`** — Numerical computing
* **`pyarrow`** — Columnar data format, interop with Pandas/Polars
* **`duckdb`** — SQL on dataframes, very fast for large datasets
* **`sqlalchemy`** — ORM for database access
* **`pyspark`** or **Databricks/Spark** — For truly massive claims datasets (100M+ rows)

**When to use:**
- Pandas: < 10GB, standard workflow
- Polars: 10–100GB, need speed
- Spark: > 100GB or distributed compute needed

## Machine learning

* **`scikit-learn`** — Standard ML library
  - IsolationForest
  - LocalOutlierFactor
  - OneClassSVM
  - RobustScaler, preprocessing pipelines
  
* **`xgboost`** — Gradient boosting (fast, accurate)
* **`lightgbm`** — Faster gradient boosting
* **`catboost`** — Gradient boosting with categorical feature support

**For rebate anomaly detection, scikit-learn's IsolationForest is the standard implementation for unsupervised anomaly scoring on tabular data.**

## Anomaly detection specialized libraries

* **`pyod`** — Python Outlier Detection library
  - Includes Isolation Forest, LOF, SVM, clustering-based, ensemble methods
  - Excellent for comparing multiple algorithms
  
* **`adtk`** — Anomaly Detection Toolkit
  - Time-series anomaly detection
  
* **`sktime`** — Time-series machine learning
  - Forecasting, classification, anomaly detection
  
* **`darts`** — Another time-series library
  
* **`ruptures`** — Change-point detection
  
* **`river`** — Online/streaming anomaly detection
  
* **`alibi-detect`** — Multiple anomaly detection algorithms
  
* **`deepod`** — Deep learning-based outlier detection

## Time-series and change-point detection

* **`statsmodels`** — Statistical models
  - ARIMA, SARIMA, exponential smoothing
  - Seasonal decomposition
  
* **`prophet`** — Facebook's forecasting tool
  - Good for automated forecasting with seasonality
  
* **`darts`** — Covered above; has time-series methods
  
* **`sktime`** — Covered above
  
* **`ruptures`** — Change-point detection (e.g., detect quarter when rebate dropped)
  
* **`kats`** — Meta's time-series library (if supported in your environment)
  
* **`river`** — Streaming/online anomaly detection

## Explainability and interpretability

* **`shap`** — SHapley Additive exPlanations
  - Feature importance for tree-based models
  - SHAP values show marginal impact of each feature
  
* **`lime`** — Local Interpretable Model-agnostic Explanations
  - Model-agnostic interpretation
  
* **`eli5`** — Explain Like I'm 5
  - Decision tree visualization, feature importance
  
* **`sklearn.inspection`** — Built into scikit-learn
  - Partial dependence, permutation importance

## Optimization and hyperparameter tuning

* **`optuna`** — Automated hyperparameter optimization
* **`hyperopt`** — Hyperparameter search
* **`scikit-optimize`** — Bayesian optimization

## Visualization and monitoring

* **`matplotlib`** — Basic plotting
* **`plotly`** — Interactive, web-based plots
* **`altair`** — Grammar of graphics, excellent for exploratory analysis
* **`seaborn`** — Statistical visualization on top of matplotlib
* **`evidently`** — ML model monitoring (data drift, performance drift)
* **`whylogs`** — Data quality and logging
* **`great_expectations`** — Data quality assertions
* **`pandera`** — Schema validation for DataFrames

## Workflow and deployment

* **`mlflow`** — Track experiments, package models
* **`prefect`** — Workflow orchestration (Airflow alternative)
* **`airflow`** — Workflow orchestration (Apache)
* **`dagster`** — Modern data orchestration
* **`dbt`** — Data transformation
* **`great_expectations`** — Data quality (mentioned above, also deployment)
* **`pandera`** — Schema validation
* **`pydantic`** — Data validation
* **`fastapi`** — Web API for serving models

## Recommended stack for rebate anomaly detection

### Minimum viable stack

```python
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
```

This gets you to Phase 2 (rules + statistical + basic ML).

### Production stack

```python
# Data
import pandas as pd
import polars as pl  # optional: faster for large data
import sqlalchemy

# ML
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb  # for Phase 4 supervised model

# Explainability
import shap

# Workflow
import airflow  # or prefect/dagster
import mlflow

# Visualization
import plotly
import seaborn as sns

# Monitoring
import evidently
from great_expectations import dataset
```

### Data science notebooks

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline

import shap

# Jupyter-specific
from IPython.display import display
import ipywidgets
```

## Installation example

```bash
# Core data + ML
pip install pandas numpy scikit-learn

# Specialized
pip install pyod shap

# Workflow (choose one)
pip install prefect

# Visualization
pip install plotly seaborn matplotlib

# Data quality
pip install great_expectations pandera
```

## Version pinning

For production, pin versions:

```txt
pandas==2.0.3
scikit-learn==1.3.0
numpy==1.24.3
pyod==1.0.5
shap==0.42.1
xgboost==1.7.5
prefect==2.13.0
plotly==5.14.1
```

## When to upgrade

- Security patches: immediately
- Bug fixes: within 2 weeks
- Major versions: after testing on non-prod

Avoid upgrading during active project cycles.

## Free tier data science tools

* **Jupyter** — Notebooks (free, self-hosted or cloud)
* **VS Code** — IDE (free)
* **GitHub** — Version control (free for private repos)
* **DuckDB** — Local analytics database (free, open source)
* **Plotly Community** — Interactive plots (free tier)

**Total cost to get started: $0 (if using cloud compute is free tier or internal)**
