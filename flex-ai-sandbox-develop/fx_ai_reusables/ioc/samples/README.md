#Prerequisites

```bash
pip3 install -r requirements.txt -r ./fx_ai_reusables/ioc/samples/samples-requirements.txt
```


Set startup object to : 

    fx_ai_reusables/ioc/samples/ioc_sample_entrypoint.py

Set environment variable (in your IDE or via command line)

DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL

You can also use a value of K8DEPLOYED or GITWORKFLOWDEPLOYED

...

Run the ioc_sample_entrypoint.py


Logs will look like this:

2025-09-22 16:39:44,285 INFO Calling animal manager speak method
2025-09-22 16:39:44,285 INFO Animal says: Woof!
2025-09-22 16:39:44,285 INFO ioc_sample_entrypoint.py has completed.

...

MyCompositionRoot (fx_ai_reusables/ioc/samples/ioc/composition_root.py)
has the "basic" IoC wire up.
Where the value of DEPLOYMENT_FLAVOR picks which concrete IAnimalManager to use.


fx_ai_reusables/ioc/samples/business_layer/composers/some_composer_concrete.py
SomeComposerConcrete

shows how to inject the IAnimalManager interface via a constructor.

SomeComposerConcrete and ISomeComposer are also defined/mapped in the MyCompositionRoot.

