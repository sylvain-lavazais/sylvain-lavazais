.DEFAULT_GOAL := help
APPLICATION_TITLE := Personal Profile on GH \n ======================
THM_USERNAME := Li77leSh4rk

.PHONY:update-thm-badge push-thm-badge help

##  ---
##@ Run
##  ---

update-thm-badge: .resolve-deps ## update tryHackMe badge
	@echo "=> $@"
	@./script/scrap_thm_profile.py $(THM_USERNAME)

push-thm-badge: update-thm-badge ## update and push tryHackMe badge
	@echo "=> $@"
	@git add tryHackMe.png
	@git commit -m "feat(THM): update tryHackMe badge [Skip GitHub Action]" || true
	@git push || true

##  ----
##@ Misc
##  ----

.resolve-deps:
	@echo "=> $@"
	@pip install -r ./script/requirements.txt

# See https://www.thapaliya.com/en/writings/well-documented-makefiles/
help: ## Display this help
	@awk 'BEGIN {FS = ":.* ##"; printf "\n\033[32;1m ${APPLICATION_TITLE}\033[0m\n\n\033[1mUsage:\033[0m\n  \033[31mmake \033[36m<option>\033[0m\n"} /^[%a-zA-Z_-]+:.* ## / { printf "  \033[33m%-25s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' ${MAKEFILE_LIST}
##@
