fyi - i added a branch rule that we can only PR into main, might be especially useful in later stages when we deploy on vercel because it automatically assumes main as the live branch. dev branch is where we can put our work together prior going into live

IDEALLY the branch flow would be:
feat/{feature-name} -> PR'd into -> dev -> PR'd into -> main