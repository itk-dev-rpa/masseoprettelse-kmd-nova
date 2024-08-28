# Masseoprettelse i KMD Nova
An Open Orchestrator RPA solution for reading emails sent from OS2 Forms and outputting notes in KMD Nova.

## Quick start

Install the robot in Open Orchestrator, with a list of accepted AZ idents for people who should be allowed to input data from OS2 Forms:

```json
{
    "accepted_azs" : ["az00000", "az000001"]
}
```

Setup email and link to Open Orchestrator queue in config.py and setup Nova access in Open Orchestrator credentials.

When the robot is run from OpenOrchestrator the `main.py` file is run which results
in the following:
1. The working directory is changed to where `main.py` is located.
2. A virtual environment is automatically setup with the required packages.
3. The framework is called passing on all arguments needed by [OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator).

## Requirements
Minimum python version 3.10

## Linting and Github Actions

This template is also setup with flake8 and pylint linting in Github Actions.
This workflow will trigger whenever you push your code to Github.
The workflow is defined under `.github/workflows/Linting.yml`.

