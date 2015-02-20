default:
	@echo -n

data: data/agency-list.csv data/agency-info.csv data/deficiencies.csv

data/agency-list.csv: scripts/get-agency-list.sh
	./scripts/get-agency-list.sh > $@

data/agency-info.csv: data/agency-list.csv scripts/scrape-basic-info.py
	./scripts/scrape-basic-info.py > $@

data/deficiencies.csv: data/agency-list.csv scripts/scrape-deficiencies.py
	./scripts/scrape-deficiencies.py > $@
