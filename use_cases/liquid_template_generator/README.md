### Liquid Template Generator


Setup:

Install the packages, using 2 .txt files.

```bash

pip install -r requirements.txt -r use_cases/liquid_template_generator/use-case-requirements.txt

or

pip3 install -r requirements.txt -r use_cases/liquid_template_generator/use-case-requirements.txt


```


Start the app (it runs via streamlit).  It will open a browser.  Note that the path here is so that it can find the reusables.  Without that, streamlit was giving runtime errors about not being able to find them.

```bash

export PYTHONPATH=$(pwd)
export DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL 
streamlit run use_cases/liquid_template_generator/app.py

```

or - run it as a python module.  this seems to let python run it/handle the relative dependencies/set the correct start path:

```bash

export DEPLOYMENT_FLAVOR=DEVELOPMENTLOCAL 

and then one of the below:


python -m streamlit run ./use_cases/liquid_template_generator/app.py

or 

python3 -m streamlit run ./use_cases/liquid_template_generator/app.py

```



Sample data:

Input Data:
```
MemberID|FirstName|LastName|Gender|DOB|ProviderName|ProviderSpecialty|Condition|Treatment|AdmissionDate|DischargeDate  
1001|Aaliyah|Nguyen|Female|1987-03-22|Dr. Priya Shah|Cardiology|Hypertension|Amlodipine|2024-03-12|2024-03-15  
1002|Diego|Martinez|Male|1990-10-15|Dr. Kevin O'Malley|Endocrinology|Type 2 Diabetes|Insulin Therapy|2024-05-01|2024-05-07  
1003|Fatima|Al-Farsi|Female|1975-06-30|Dr. Ming Zhao|Orthopedics|Fractured Tibia|Open Reduction and Internal Fixation|2024-06-10|2024-06-21  
1004|Marcus|Okafor|Male|2002-12-05|Dr. Laura Kline|Pediatrics|Asthma|Inhaled Corticosteroids|2024-04-18|2024-04-20  
1005|Sofia|Rossi|Female|1968-08-14|Dr. Ahmed El-Tayeb|Oncology|Breast Cancer|Radiation Therapy|2024-02-15|2024-03-05  
```

Output formats:

```
{
  "firstName": "John",
  "lastName": "Doe",
  "age": 21
}
```

```
{
  "firstName": "John",
  "lastName": "Doe",
  "age": 21
  "ageDESC": "young"
}
```
the logic for ageDESC, if age <40, ageDESC is 'young' and if age >=40, ageDESC is 'old'



```
{
  "title": "Person",
  "type": "object",
  "properties": {
    "firstName": {
      "type": "string",
      "description": "The person's first name."
    },
    "lastName": {
      "type": "string",
      "description": "The person's last name."
    },
    "age": {
      "description": "Age in years which must be equal to or greater than zero.",
      "type": "integer",
      "minimum": 0
    }
  }
}
```

```
{
  "title": "Person",
  "type": "object",
  "properties": {
    "firstName": {
      "type": "string",
      "description": "The person's first name."
    },
    "lastName": {
      "type": "string",
      "description": "The person's last name."
    },
    "age": {
      "description": "Age in years which must be equal to or greater than zero.",
      "type": "integer",
      "minimum": 0
    },
   "ageDESC": {
      "description": "Says 'young' or 'old' based on age value. If age <40, 'young'  if age >=40 it is 'old'  ",
      "type": "integer",
      "minimum": 0
    }
  }
}
```
