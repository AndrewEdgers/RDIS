from app.forecasting.jobs import run_indicator_forecasting
from app.ingestion.jobs import run_industrial_parks_history_ingestion
from app.normalization.jobs import run_industrial_parks_history_normalization
from app.storage.jobs import run_indicator_storage


def main():
    print("RDIS: starting ingestion")
    clean_output_paths = run_industrial_parks_history_ingestion()
    print("RDIS: starting normalization")
    normalized_indicators_path = run_industrial_parks_history_normalization(clean_output_paths)
    print("RDIS: starting storage")
    run_indicator_storage(normalized_indicators_path)
    print("RDIS: starting forecasting")
    run_indicator_forecasting()


if __name__ == "__main__":
    main()
