# RDIS

Regional Development Indicator System

## Overview

RDIS is a prototype decision-support system designed to collect, process, and analyze regional development indicators across Ukraine. The goal is to support comparative regional analysis and enable predictive insights based on economic and social indicators.

The system automatically retrieves open government datasets and prepares them for further analytical processing and visualization.

This project is being developed as part of a Master's capstone focused on data-driven regional analysis and predictive modeling.

## Objectives

The system aims to:

* Collect regional development indicators from open data sources
* Store and organize datasets in a structured format
* Enable comparative analysis between regions
* Support predictive modeling of regional development indicators
* Provide a foundation for an interactive analytical dashboard

The long-term goal is to build a scalable decision-support tool for policymakers, researchers, and regional development organizations.

## Current Status (MVP Phase)

The current prototype implements the first stage of the data pipeline:

1. Retrieval of dataset metadata from the Ukrainian open data portal (data.gov.ua)
2. Parsing dataset metadata via API
3. Local storage of retrieved dataset information

Future development stages will include automated dataset downloading, data normalization, database storage, predictive modeling, and dashboard visualization.

## Technologies

* Python 3.12
* Requests (API communication)
* JSON processing
* Open Government Data API (data.gov.ua)

Planned technologies:

* SQLite → PostgreSQL (scalable database layer)
* Pandas (data processing)
* Scikit-learn / statistical models (predictive analytics)
* Streamlit or similar dashboard framework

## Data Sources

Primary data sources include Ukrainian open government data portals:

* https://data.gov.ua
* https://stat.gov.ua

## Indicators (Initial Set)

Economic Vector

* Gross Regional Product per capita
* Industrial production index
* Capital investments
* Export of goods

Labor Market

* Average nominal wage
* Real wage index

Macroeconomics

* Consumer price index

Business Development

* Number of industrial parks

Social Vector

* Share of children enrolled in preschool education

These indicators will form the basis of regional comparison and predictive analysis.

## Roadmap

Phase 1 — Data Ingestion

* API integration
* dataset discovery
* automated downloads

Phase 2 — Data Processing

* data cleaning
* normalization
* indicator aggregation

Phase 3 — Storage Layer

* SQLite database
* schema design for regional indicators

Phase 4 — Predictive Models

* regional trend forecasting
* risk scoring for development indicators

Phase 5 — Dashboard

* interactive regional comparison
* indicator visualization
* predictive analytics interface

## License

This project is released under the RDIS Non-Commercial License.

Use, modification, and distribution are permitted for academic, research, and other non-commercial purposes.

Commercial use of this software or any derivative work requires explicit permission from the author.

Open datasets used in this project remain subject to their respective licenses.