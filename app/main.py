from app.ingestion.jobs import run_industrial_parks_ingestion


def main():
    print("RDIS: starting ingestion")
    run_industrial_parks_ingestion()


if __name__ == "__main__":
    main()