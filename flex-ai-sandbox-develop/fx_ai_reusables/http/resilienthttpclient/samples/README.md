


```bash
pip3 install -r requirements.txt -r ./fx_ai_reusables/http/resilienthttpclient/samples/samples-requirements.txt
```

PREREQUISITES:

    podman pull edgeinternal1uhg.optum.com/glb-docker-vir/kennethreitz/httpbin

    podman run --publish 8798:80 --name httpbinContainerName1 edgeinternal1uhg.optum.com/glb-docker-vir/kennethreitz/httpbin



RUN:

    fx_ai_reusables/http/resilienthttpclient/samples/resilient_http_client_sample.py