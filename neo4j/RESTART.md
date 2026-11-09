If the laptop sleeps, reboots, or the Neo4j window gets closed before the defense, restart both pieces
from a WSL terminal:

```bash
export JAVA_HOME=~/opt/jdk-21.0.13+9
export PATH=$JAVA_HOME/bin:$PATH
cd ~/opt/neo4j-community-5.26.0
nohup bin/neo4j console > /tmp/neo4j_console.log 2>&1 &
disown
```

Wait a few seconds (`curl -sI http://localhost:7474` should return `200 OK`), then reopen the browser
window:

```bash
export DISPLAY=:0
nohup ~/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome \
  --new-window --start-maximized \
  --user-data-dir="$HOME/.neo4j-demo-chrome-profile" \
  "http://localhost:7474/browser/" > /tmp/chrome_launch.log 2>&1 &
disown
```

The data persists on disk (`~/opt/neo4j-community-5.26.0/data`) and your saved Favorites persist in the
Chrome profile (`~/.neo4j-demo-chrome-profile`), so nothing needs reloading -- just the two processes
need to be running again. If something looks wrong, reload from scratch with:

```bash
cd ~/opt/neo4j-community-5.26.0 && export JAVA_HOME=~/opt/jdk-21.0.13+9 && export PATH=$JAVA_HOME/bin:$PATH
bin/cypher-shell -a bolt://localhost:7687 -u neo4j -p "" "MATCH (n) DETACH DELETE n;"
bin/cypher-shell -a bolt://localhost:7687 -u neo4j -p "" -f /home/ryanebanda/workspace/graph-analytics-13f-coholding/neo4j/load.cypher
```
