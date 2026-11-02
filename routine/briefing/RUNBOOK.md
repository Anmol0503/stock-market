# Morning Briefing: runbook for the scheduled cloud run

This is an **unattended** run. Do the steps below in order and nothing else: don't ask questions, don't edit
files by hand, don't read files under `output/` (they are large and not for you), and **never** run
`git add -A`, `git add .` or `git checkout -- .`. The pipeline is code; your job is to keep it running and
publish the result.

1. **Setup** (about 1–2 minutes):
   `git fetch -q origin main && git checkout -q -B main origin/main && python3 -m pip install -q -r routine/briefing/requirements.txt`

2. **Build the edition.** Run this command with a Bash timeout of 600000 ms:
   `python3 -m routine.briefing next`
   It prints exactly one line:
   - `NEXT <stage> …`: still working. Run the same command again.
   - `DONE <status>`: finished; go to step 3.
   - `FAILED <reason>`: run it once more (it resumes from where it stopped). If it fails again, go to step 3
     anyway.
   Repeat at most 30 times. Don't run anything else while it's working.

3. **Publish** (always, even after FAILED: it still commits the quality report):
   `python3 -m routine.briefing publish`

4. **Report**: run `python3 -m routine.briefing summary` and make its output your final message, plus the
   publish line from step 3 verbatim.

If a command errors in a way not covered here, don't improvise fixes: include the exact error in your final
message.
