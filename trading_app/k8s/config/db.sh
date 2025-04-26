# Replace with your actual connection details
PGHOST=db-postgresql-nyc3-foundary-do-user-21263709-0.j.db.ondigitalocean.com
PGPORT=25060  # Default DO port
PGUSER=doadmin
PGPASSWORD=AVNS_VN880hV484uy523rqrS
PGDATABASE=defaultdb

# Run the scripts
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f db-schemas.sql
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f db-data.sql