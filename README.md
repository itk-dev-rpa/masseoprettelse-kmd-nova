# Masseoprettelse i KMD Nova
An Open Orchestrator RPA solution for reading emails sent from OS2 Forms and outputting notes in KMD Nova.

The robot will read the emails from the inbox, create queue elements and then run through each queue element and create notes in Nova.

## Quick start

Install the robot in Open Orchestrator, with a list of accepted AZ idents for people who should be allowed to input data from OS2 Forms:

```json
{
    "accepted_azs" : ["az00000", "az000001"]
}
```

Setup email and link to Open Orchestrator queue in config.py and setup Nova access in Open Orchestrator credentials.

## Known errors

If a non-CPR is found in input (such as a line with headers), the robot will fail.

## Requirements
Minimum python version 3.10

## Linting and Github Actions

This template is also setup with flake8 and pylint linting in Github Actions.
This workflow will trigger whenever you push your code to Github.
The workflow is defined under `.github/workflows/Linting.yml`.

