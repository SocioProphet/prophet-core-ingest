.PHONY: validate validate-wallguard-ingest-labels

validate: validate-wallguard-ingest-labels

validate-wallguard-ingest-labels:
	python3 tools/validate_wallguard_ingest_labels.py
