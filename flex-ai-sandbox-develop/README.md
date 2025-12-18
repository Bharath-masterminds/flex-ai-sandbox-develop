# Azure OpenAI Starter Kit

A starter kit for working with Azure OpenAI and LangChain.


# "New Idea" Branching Strategy


Create a NEW feature/X branch from main.

For the code in your feature/X branch:

Create a SUBFOLDER in folder-file-structure of the project, to avoid putting everything in the root folder.




Make your changes in your feature/X branch.

Use a short but good name for "X", do not call it "proof1" or other ambiguous names.

Create a PR 'feature/X to main'


DO NOT MERGE IT.
Label it with "do not merge" in the gitHub PR.

In the PR description, describe what the 


If you create a "utility helper" that ~~any AI project could benefit from,
you can create a separate feature/Y branch, with the intention to merge it to 'main'


For example:

A .py file that loads (any) .xml file or any .json file.
That can be merged to 'main' (use a separate isolated feature/Y branch and PR)

A .py file that has YOUR AI-Idea specific code, never merge to 'main'


## Folder Structure

The below folder should have code that works with any/all "use-case"

./reusables/

Do not put code at the root-level of "./reusables/".  Create some sub-module/sub-folder(s).


Examples of "reusables".  Read/load the xml from any .xml file.  Read/load json from any .json file.  Read/load environment variables from a .env file.

...

./use_cases/

Create a sub-folder under "./use_cases/" for your specific use-case.

Do not put code at the root-level of "./use_cases/".  Create some sub-module/sub-folder(s).

Here is where you put your specific AI use-case code.  Give the sub-folder a good name, that describes the use-case.

If you think you might have "multiple-tries", then add a suffix like "One", "Two", "Three" to the sub-folder name.

For example, a real world example would be: 


./use_cases/math_functionality_version_one



Now, you may want to do a double-folder structure, like:

./use_cases/liquid_templates/fhir_liquid_template_version_one/


In this case, you may have some reusable code pieces that might be shared between similar use-cases.


./use_cases/liquid_templates/hl7v2_liquid_template_version_one/


And now if there is code that could be shared between "fhir_liquid_template_version_one" AND "hl7v2_liquid_template_version_one", BUT is NOT "any/every use case" appropriate,
then you can create

./use_cases/liquid_templates/use_case_family_reusable/


Separation of code is "an art", but let's try to keep things separate at the:

./reusables/ - for any/all use-cases

./use_cases/my_use_case_family/
./use_cases/my_use_case_family/concrete_one/
./use_cases/my_use_case_family/concrete_two/
./use_cases/my_use_case_family/use_case_family_reusable/




Now, once inside the 

./use_cases/my_use_case_family/concrete_one/

folder/sub-module,

you do not have to put all files at that level.

Use more sub-folders under "concrete_one" to organize your code.


More concrete example:

./use_cases/liquid_templates/fhir_liquid_template_version_one/

./use_cases/liquid_templates/hl7v2_liquid_template_version_one/

(below is anything shareable between FHIR and HL7v2 liquid templates, but NOT ./reusables/)

./use_cases/liquid_templates/liquid_reusable/


#### README

Please create a README.md file under each use-case sub-folder.

example:

./use_cases/my_use_case_family/concrete_one/README.md

It should give a brief description of the use-case, and how to run it.



#### "requirements.txt"

to avoid the (root folder) requirements.txt from having every package for every use-case, please follow the below guideline.

under your:

./use_cases/my_use_case_family/concrete_one/

create a file called:

use-case-requirements.txt

then update your use-case README to have instructions like below:

pip3 install -r requirements.txt -r ./use_cases/liquid_templates/fhir_liquid_template_version_one/use-case-requirements.txt


Concrete example:

If I were working on 'fhir_liquid_template_version_one', then I would create:

./use_cases/liquid_templates/fhir_liquid_template_version_one/use-case-requirements.txt

In the above file, I might put a library-reference like:

ShopifyAPI


because "ShopifyAPI" would pertain to my use-case, but not any/every/all use-cases.


and add this "install multiple files" line/syntax to the README.md of that use-case:

```bash

pip3 install -r requirements.txt -r ./use_cases/liquid_templates/fhir_liquid_template_version_one/use-case-requirements.txt

```



## Setup Instructions

### 1. Create a Virtual Environment

In your IDE Terminal (or outside)

```bash
# Create a virtual environment
python -m venv .venv
or
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source ./.venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

Note, after you "activate" your .venv
your command prompt should have "(.venv") as the prefix.

Do not continue to 'pip' if you do not have this.


### 2. Install Dependencies

```bash
pip install -r requirements.txt -r fx_ai_reusables/requirements.txt

or

pip3 install -r requirements.txt -r fx_ai_reusables/requirements.txt
```

### 3. Environment Variables

Make sure to set up your `.env` file with the required Azure OpenAI and other service credentials. An example template is provided in the repository.

Aka, copy and paste .env.example to '.env'.
Note, ".env" is in .gitignore.  So you should NEVER CHECK IN your .env file.
If you do, you will compromise the secrets.


For the values needed for the ENV variables, please reach out to FHIR Marshalls or other team members who have done some AI for the location of the values.


### 4. Running the Notebook

From Terminal, No IDE:

```bash
jupyter notebook
```

### 5. Running "langchain" .py 

In your IDE.

Right-Click / Run (the below file)

langchain_azure_openai.py

Note, without any command-line arguments, it will use the default-prompt.

In your IDE (VS-Code, Pycharm), you can add command-line-argument.
Put the sentence in quotes.

for example.

"What are the most popular fast food restaurants in the world?"

### 6. Running "langgraph" .py 

In your IDE.

Right-Click / Run (the below file)

langgraph_azure_openai.py





### 7. Running "Jupyter" in VS Code

OR in VS Code:

Open the file:

langchain_azure_openai.ipynb

in upper right window find "Select Kernel"
Select "Python Environments..."
"+Create Python Environment"
"Venv Creates a '.venv' virtual environment in the current workspace"

"Use Existing Use existing '.venv' environment with no changes to it"

If "Use Existing" does not work:

Instead of "Use Existing ____________"
choose
"Delete and Recreate Delete existing ".venv" directory and create a new ".venv" environment".

Note, if you "Delete and Recreate", you'll need to re-run the pip (or pip3) command.



### 8 Add new "hello-world" jupyter.

Go to "Command Palette"

"Create: New Jupyter Notebook"

This gives you a default file "Untitled-1.ipynb"

Save (as)
  hellow-world-sample.ipynb 

Note, we are by-passing the "use_cases" sub-folder/sub-module guidelines for this simple hello-world example.

It will default to a single "Code" window, with the language as "Python".  (Look for "Pyton" in the lower right of the code-window)

paste the follow code inside the (python) code window


```python
from datetime import datetime
print("hello world", datetime.now().strftime("%H:%M:%S"))
```

For each new ".ipynb" window, you will have to "Select Kernel".  Try to use the existing '.venv', but you may have to Delete-And-Recreate.

Click the "Run All" button.

### 9 Add .py module and call using jupyter

Add a new sub-folder for your use-case:

./use_cases/math/math_version_one/


Add new file:

Save (as):

./use_cases/math/math_version_one/MathUtils.py

Paste in the following code:

```python
class MathUtils:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def subtract(a, b):
        return a - b

    @staticmethod
    def multiply(a, b):
        return a * b

    @staticmethod
    def divide(a, b):
        if b == 0:
            return "Cannot divide by zero"
        return a / b
```



Go to "Command Palette"

"Create: New Jupyter Notebook"

This gives you a default file "Untitled-1.ipynb"

Save (as)
  ./use_cases/math/math_version_one/math-sample.ipynb 

It will default to a single "Code" window, with the language as "Python".  (Look for "Pyton" in the lower right of the code-window)

paste the follow code inside the (python) code window


```python
from MathUtils import MathUtils

res = MathUtils.add(10, 5) # Output: 15
print(res)

res = MathUtils.subtract(10, 5) # Output: 5
print(res)

res = MathUtils.multiply(10, 5) # Output: 50
print(res)

res = MathUtils.divide(10, 5) # Output: 2.0
print(res)

```

Try to "Run All" (the math-sample.ipynb)

Note, you may need to "Restart" (Restart the Kernel) using the VS Code "Restart" button at the top of the ipynb editor.  (Note, you won't see "Restart" if you don't have a Kernel selected)


The lesson of MathUtils is that you can put python code in .py files.  You do NOT have to put all the code in the .ipynb jupyter file.

Note, the methods of MathUtils.py are all static methods.


### 10.  Run MathUtils via a python Runner

Add   ./use_cases/math/math_version_one/MathUtils.py (from above)

Add new class

  ./use_cases/math/math_version_one/MathExampleEntryPoint.py

paste the following code

```python

from MathUtils import MathUtils
import asyncio


async def main():

    res = MathUtils.add(10, 5) # Output: 15
    print(res)

    res = MathUtils.subtract(10, 5) # Output: 5
    print(res)

    res = MathUtils.multiply(10, 5) # Output: 50
    print(res)

    res = MathUtils.divide(10, 5) # Output: 2.0
    print(res)


# Run the main function
asyncio.run(main())

```

Right-click/Run 'MathExampleEntryPoint.py'


### In General Tips.

(Especially in VS-Code, Pycharm seems a little less finicky)

anytime you change a .py file, you may need to restart the Kernel.

anytime you change/add an entry into requirements.txt, you need to run pip/pip3, and after you run pip/pip3, you may need to restart the Kernel.

anytime you change an ENV variable (aka, edit .env file), you may need to restart the Kernel.

Aka, because python is not a compiled code base, it (the changes that the running Kernel "sees") .... is "finicky".


....


When you create a Kernel, you pick a version of Python.  Note, "latest and greatest" version of Python may not be the best choice.

This code was tested against v 3.10.18.  (Even though v 3.13.x was available)

libraries in "requirements.txt" are sensitive to python runtime version.