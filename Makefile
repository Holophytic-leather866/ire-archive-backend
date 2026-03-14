PYTHON ?= uv run python
ARGS ?=

.PHONY: dev-start dev-stop dev-restart dev-status dev-logs dev-index dev-index-test dev-clear-db dev-rebuild dev-clear-cache dev-test dev-test-backend \
        prod-push prod-status prod-logs prod-ssh prod-restart prod-clear-cache prod-stats prod-index prod-verify-ids prod-rebuild prod-scale prod-build-base \
        setup-install setup-init-prod

# --------- Local development ---------

dev-start:
	$(PYTHON) -m scripts.dev_tasks start $(ARGS)

dev-stop:
	$(PYTHON) -m scripts.dev_tasks stop $(ARGS)

dev-restart:
	$(PYTHON) -m scripts.dev_tasks restart $(ARGS)

dev-status:
	$(PYTHON) -m scripts.dev_tasks status $(ARGS)

dev-logs:
	$(PYTHON) -m scripts.dev_tasks logs $(ARGS)

dev-index:
	$(PYTHON) -m scripts.dev_tasks index $(ARGS)

dev-index-test:
	$(PYTHON) -m scripts.dev_tasks index-test $(ARGS)

dev-clear-db:
	$(PYTHON) -m scripts.dev_tasks clear-db $(ARGS)

dev-rebuild:
	$(PYTHON) -m scripts.dev_tasks rebuild $(ARGS)

dev-clear-cache:
	$(PYTHON) -m scripts.dev_tasks clear-cache $(ARGS)

dev-test:
	$(PYTHON) -m scripts.dev_tasks test $(ARGS)

dev-test-backend:
	$(PYTHON) -m scripts.dev_tasks test-backend $(ARGS)

# --------- Production ---------

prod-push:
	$(PYTHON) -m scripts.prod_tasks push $(ARGS)

prod-status:
	$(PYTHON) -m scripts.prod_tasks status $(ARGS)

prod-logs:
	$(PYTHON) -m scripts.prod_tasks logs $(ARGS)

prod-ssh:
	$(PYTHON) -m scripts.prod_tasks ssh $(ARGS)

prod-restart:
	$(PYTHON) -m scripts.prod_tasks restart $(ARGS)

prod-clear-cache:
	$(PYTHON) -m scripts.prod_tasks clear-cache $(ARGS)

prod-stats:
	$(PYTHON) -m scripts.prod_tasks stats $(ARGS)

prod-index:
	$(PYTHON) -m scripts.prod_tasks index $(ARGS)

prod-verify-ids:
	$(PYTHON) -m scripts.prod_tasks verify-ids $(ARGS)

prod-rebuild:
	$(PYTHON) -m scripts.prod_tasks rebuild $(ARGS)

prod-scale:
	$(PYTHON) -m scripts.prod_tasks scale $(ARGS)

prod-build-base:
	$(PYTHON) -m scripts.prod_tasks build-base $(ARGS)

# --------- Setup ---------

setup-install:
	$(PYTHON) -m scripts.setup_tasks install $(ARGS)

setup-init-prod:
	$(PYTHON) -m scripts.setup_tasks init-prod $(ARGS)
