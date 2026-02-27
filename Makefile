SHELL := /bin/bash

PYTHON ?= python

PRIMARY_CONFIG ?= configs/primary/chest_chexpert.yaml
POC_CONFIG ?= configs/poc/chest_pneumonia_binary.yaml
INFER_CONFIG ?= $(POC_CONFIG)
IMAGE ?=

.PHONY: help install \
	train-primary resume-primary eval-primary \
	train-poc resume-poc eval-poc \
	infer streamlit \
	sanity-primary sanity-poc \
	eta-primary eta-poc \
	eta-primary-watch eta-poc-watch \
	gcp-build-image gcp-submit-primary gcp-submit-poc gcp-ops

help:
	@echo "Targets:"
	@echo "  make train-primary       # Train with $(PRIMARY_CONFIG)"
	@echo "  make resume-primary      # Resume from outputs/chest_baseline/checkpoints/last.pt"
	@echo "  make eval-primary        # Eval test split for $(PRIMARY_CONFIG)"
	@echo "  make train-poc           # Train with $(POC_CONFIG)"
	@echo "  make resume-poc          # Resume from outputs/poc/chest_pneumonia_binary/checkpoints/last.pt"
	@echo "  make eval-poc            # Eval test split for $(POC_CONFIG)"
	@echo "  make sanity-primary      # Run data sanity checks for primary config"
	@echo "  make sanity-poc          # Run data sanity checks for POC config"
	@echo "  make eta-primary         # One-shot ETA readout for primary run"
	@echo "  make eta-poc             # One-shot ETA readout for POC run"
	@echo "  make eta-primary-watch   # Live ETA watcher for primary run"
	@echo "  make eta-poc-watch       # Live ETA watcher for POC run"
	@echo "  make streamlit           # Launch app via python -m streamlit"
	@echo "  make infer IMAGE=/path/to/image.jpg [INFER_CONFIG=...]"
	@echo "  make gcp-build-image     # Build/push RAV training image to Artifact Registry"
	@echo "  make gcp-submit-primary  # Submit primary (CheXpert) spot run via gcp-spot-runner"
	@echo "  make gcp-submit-poc      # Submit POC spot run via gcp-spot-runner"
	@echo "  make gcp-ops ARGS='...'  # Pass-through ops command (default: status)"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

train-primary:
	$(PYTHON) scripts/train_chest_baseline.py --config $(PRIMARY_CONFIG)

resume-primary:
	$(PYTHON) scripts/train_chest_baseline.py --config $(PRIMARY_CONFIG) --resume-checkpoint outputs/chest_baseline/checkpoints/last.pt

eval-primary:
	$(PYTHON) scripts/eval_chest_baseline.py --config $(PRIMARY_CONFIG) --split test

train-poc:
	$(PYTHON) scripts/train_chest_baseline.py --config $(POC_CONFIG)

resume-poc:
	$(PYTHON) scripts/train_chest_baseline.py --config $(POC_CONFIG) --resume-checkpoint outputs/poc/chest_pneumonia_binary/checkpoints/last.pt

eval-poc:
	$(PYTHON) scripts/eval_chest_baseline.py --config $(POC_CONFIG) --split test

infer:
	@if [ -z "$(IMAGE)" ]; then \
		echo "Usage: make infer IMAGE=/absolute/path/to/chest_xray.jpg [INFER_CONFIG=configs/...yaml]"; \
		exit 1; \
	fi
	$(PYTHON) scripts/infer_chest_single.py --config $(INFER_CONFIG) --image $(IMAGE)

streamlit:
	$(PYTHON) -m streamlit run app/streamlit_app.py

sanity-primary:
	$(PYTHON) scripts/check_chest_data_sanity.py --config $(PRIMARY_CONFIG)

sanity-poc:
	$(PYTHON) scripts/check_chest_data_sanity.py --config $(POC_CONFIG)

eta-primary:
	$(PYTHON) scripts/monitor_training_eta.py --config $(PRIMARY_CONFIG)

eta-poc:
	$(PYTHON) scripts/monitor_training_eta.py --config $(POC_CONFIG)

eta-primary-watch:
	$(PYTHON) scripts/monitor_training_eta.py --config $(PRIMARY_CONFIG) --watch --interval-seconds 10

eta-poc-watch:
	$(PYTHON) scripts/monitor_training_eta.py --config $(POC_CONFIG) --watch --interval-seconds 10

gcp-build-image:
	bash scripts/gcp_build_image.sh

gcp-submit-primary:
	bash scripts/gcp_submit_primary.sh

gcp-submit-poc:
	bash scripts/gcp_submit_poc.sh

gcp-ops:
	bash scripts/gcp_ops.sh $(ARGS)
