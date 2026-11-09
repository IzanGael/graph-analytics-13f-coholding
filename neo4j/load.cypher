// Load the co-holding "tribes" demo (conviction graph) -- defense demo only, not graded pipeline data.
// Run with: cypher-shell -f neo4j/load.cypher   (auth disabled on this local instance)

CREATE CONSTRAINT stock_id IF NOT EXISTS FOR (s:Stock) REQUIRE s.stockId IS UNIQUE;
CREATE CONSTRAINT manager_id IF NOT EXISTS FOR (m:Manager) REQUIRE m.managerId IS UNIQUE;
CREATE CONSTRAINT tribe_id IF NOT EXISTS FOR (t:Tribe) REQUIRE t.tribeId IS UNIQUE;
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///tribes.csv' AS row
MERGE (t:Tribe {tribeId: row.tribeId})
SET t.quarter = row.quarter, t.groupNum = toInteger(row.groupNum),
    t.name = row.name, t.sizeFull = toInteger(row.size_full);

LOAD CSV WITH HEADERS FROM 'file:///managers.csv' AS row
MERGE (m:Manager {managerId: row.managerId})
SET m.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///stocks.csv' AS row
MERGE (s:Stock {stockId: row.stockId})
SET s.quarter = row.quarter, s.issuer = row.issuer, s.name = row.name, s.ticker = row.ticker,
    s.sector = row.sector, s.valueBn = toFloat(row.value_bn), s.bettors = toInteger(row.bettors),
    s.participation = toFloat(row.participation),
    s.sceneRank = CASE row.sceneRank WHEN '' THEN null ELSE toInteger(row.sceneRank) END
MERGE (sec:Sector {name: row.sector})
MERGE (s)-[:IN_SECTOR]->(sec)
WITH s, row
MATCH (t:Tribe {tribeId: row.tribeId})
MERGE (s)-[:IN_TRIBE]->(t);

LOAD CSV WITH HEADERS FROM 'file:///co_bet.csv' AS row
MATCH (a:Stock {stockId: row.source}), (b:Stock {stockId: row.target})
MERGE (a)-[r:CO_BET]->(b)
SET r.z = toFloat(row.z), r.shared = toInteger(row.shared), r.quarter = row.quarter;

LOAD CSV WITH HEADERS FROM 'file:///bets_on.csv' AS row
MATCH (m:Manager {managerId: row.managerId}), (s:Stock {stockId: row.stockId})
MERGE (m)-[r:BETS_ON]->(s)
SET r.overweight = toFloat(row.overweight), r.quarter = row.quarter;
