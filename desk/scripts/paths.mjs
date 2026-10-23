// Where the tracker keeps its data: $TRACKER_HOME, else ~/.personal-tracker (the same rule as personal_tracker/paths.py).
import { homedir } from "node:os";
import { join } from "node:path";

export const trackerHome = (env = process.env, home = homedir()) => env.TRACKER_HOME || join(home, ".personal-tracker");
export const templatePath = (env = process.env, home = homedir()) => join(trackerHome(env, home), "desk-template.html");
