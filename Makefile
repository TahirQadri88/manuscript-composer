.PHONY: check
check:
	python3 -m pip install -q -r requirements.txt
	python3 -m unittest tests.test_skill -v
