# Trivia Night
Eleanor Fan

A playbook to make users play a trivia game before using sudo.

Disclaimer: works only when the user is in the bash shell

To configure:
- files/questions.csv contains the trivia questions
- defaults/main.yml contains:
  - users: the users to apply the change to
  - loc: where the files will be located
  - exit_text: the text to override the game

If running standalone, run: `ansible-playbook -i <interface>, --extra-vars @defaults/main.yml standalone.yaml`
