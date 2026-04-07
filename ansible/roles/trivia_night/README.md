If running standalone, run `ansible-playbook -i <inventory> --extra-vars "@defaults/main.yml" tasks/main.yml`. Note that tasks/main.yml will need to be altered so that it is valid.

To configure:
- files/questions.csv contains the trivia questions
- defaults/main.yml contains:
  - users: the users to apply the change to
  - trivia_loc: where the python will be located
  - question_loc: where the trivia questions will be located
  - exit_text: the text to override the game
