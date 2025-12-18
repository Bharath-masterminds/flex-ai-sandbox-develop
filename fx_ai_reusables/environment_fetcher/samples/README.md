#Prerequisites

```bash
pip3 install -r requirements.txt -r ./fx_ai_reusables/environment_fetcher/samples/samples-requirements.txt
```



Set startup object to : 

    fx_ai_reusables/environment_fetcher/samples/environment_fetcher_sample.py


CREATE the FILE:

    fx_ai_reusables/environment_fetcher/samples/.env

In this file, put this line:

    SAMPLE_TEST_NOT_REAL_ENVIRONMENT_VARIABLE_NAME=SAMPLE_TEST_NOT_REAL_ENVIRONMENT_VARIABLE_VALUE


Run the py file : environment_fetcher_sample.py


You should see:


    2025-10-20 17:00:45,227 INFO EmptyEnvironmentFetcherAsync.load_environment called - no action taken.

and

    2025-10-20 17:00:45,227 INFO EnvironmentFetcherAsync.load_environment called.  Looking for .env file.
    2025-10-20 17:00:45,228 INFO Environment variables loaded from .env file
    2025-10-20 17:00:45,228 INFO SAMPLE_TEST_NOT_REAL_ENVIRONMENT_VARIABLE_VALUE
