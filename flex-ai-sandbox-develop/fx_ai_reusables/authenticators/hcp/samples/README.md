


hcp_authenticator_sample.py

ConfigMaps are defined and checked in.  Secrets are not checked in.

This sample gets an hcp_token and shows how to use local-config-map-files.


.....

The CONFIG MAPS will come from 2 files:

    "hcp.authentication.configmaps.txt",
    "fx_ai_reusables/authenticators/hcp/samples/hcp.authentication.subfolder.optional.configmaps.txt",


....

The secrets will still come from ".env" file.

You will have to define the below (secret) values in your .env file

NEVER CHECK IN YOUR .env FILE TO SOURCE CONTROL!  (Or any of the below values!)


HCP_CLIENT_ID=
HCP_CLIENT_SECRET=

AZURE_OPENAI_EMBEDDINGS_API_KEY=
AZURE_APP_CLIENT_ID=
AZURE_APP_CLIENT_SECRET=
UAIS_PROJECT_ID=


...

Run hcp_authenticator_sample.py

it should create a hcp-token.