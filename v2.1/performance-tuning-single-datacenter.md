---
title: Performance Tuning (Single Datacenter)
summary:
toc: false
---

<!--
1. Reserve 4 VMs: `roachprod create jesse-crdb -n 4`
2. Put `cockroach` on first 3 (reserve the fourth for loadgen, etc.): `roachprod run jesse-crdb "curl https://binaries.cockroachdb.com/cockroach-v2.0.2.linux-amd64.tgz | tar -xvz; mv cockroach-v2.0.2.linux-amd64/cockroach cockroach"`
3. Start the cluster: `roachprod start jesse-crdb:1-3`
4. Put the file on node 1: `roachprod put jesse-crdb:1 '<path-to-local>/movr.sql' '~'``
5. SSH to node 1 and run the sql: `roachprod run jesse-crdb:1 "./cockroach sql --insecure --database=movr < movr.sql"`
-->

## Overview

### Topology

3 `n1-standard-4` VMs, each with 4 CPUs, 15GB memory, local SSD

### Performance expectations

### Schema

## Step 1. Start a 3-node cluster

Follow our [GCE deployment tutorial](deploy-cockroachdb-on-google-cloud-platform-insecure.html). Be sure to use 3 `n1-standard-4` VMs, each with 4 CPUs, 15GB memory, local SSD.

## Step 2. Import the `movr` database

SSH to node 1 and create the `movr` database:

~~~ shell
$ cockroach sql --insecure --host=<address of any node>
~~~

~~~ sql
> CREATE DATABASE movr;
~~~

~~~ sql
> USE movr;
~~~

~~~ sql
> IMPORT TABLE users (
  	id UUID NOT NULL,
  	name STRING NULL,
  	address STRING NULL,
  	credit_card STRING NULL,
  	CONSTRAINT "primary" PRIMARY KEY (id ASC),
  	FAMILY "primary" (id, name, address, credit_card)
)
CSV DATA (
    's3://cockroachdb-movr/datasets/large-csv/users/n1.0.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/users/n1.1.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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'
);
~~~

~~~ sql
> IMPORT TABLE vehicles (
  	id UUID NOT NULL,
  	type STRING NULL,
  	city STRING NOT NULL,
  	owner_id UUID NULL,
  	creation_time TIMESTAMP NULL,
  	status STRING NULL,
  	ext JSON NULL,
  	CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),
  	UNIQUE INDEX vehicles_id_key (id ASC),
  	INDEX vehicles_auto_index_fk_owner_id_ref_users (owner_id ASC),
  	INDEX ix_vehicle_type (type ASC),
  	FAMILY "primary" (id, type, city, owner_id, creation_time, status, ext)
)
CSV DATA (
    's3://cockroachdb-movr/datasets/large-csv/vehicles/n1.0.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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'
);
~~~

~~~ sql
> IMPORT TABLE rides (
  	id UUID NOT NULL,
  	rider_id UUID NULL,
  	vehicle_id UUID NULL,
  	start_address STRING NULL,
  	end_address STRING NULL,
  	start_time TIMESTAMP NULL,
  	end_time TIMESTAMP NULL,
  	revenue FLOAT NULL,
  	CONSTRAINT "primary" PRIMARY KEY (id ASC),
  	INDEX rides_auto_index_fk_rider_id_ref_users (rider_id ASC),
  	INDEX rides_auto_index_fk_vehicle_id_ref_vehicles (vehicle_id ASC),
  	FAMILY "primary" (id, rider_id, vehicle_id, start_address, end_address, start_time, end_time, revenue)
)
CSV DATA (
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.0.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.1.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.2.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.3.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.4.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.5.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.6.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.7.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.8.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
    's3://cockroachdb-movr/datasets/large-csv/rides/n1.9.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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'
);
~~~

## Step 3. Add and validate foreign key constraints

~~~ sql
> ALTER TABLE vehicles ADD CONSTRAINT fk_owner_id_ref_users FOREIGN KEY (owner_id) REFERENCES users (id);
~~~

~~~ sql
> ALTER TABLE rides ADD CONSTRAINT fk_rider_id_ref_users FOREIGN KEY (rider_id) REFERENCES users (id);
~~~

~~~ SQL
> ALTER TABLE rides ADD CONSTRAINT fk_vehicle_id_ref_vehicles FOREIGN KEY (vehicle_id) REFERENCES vehicles (id);
~~~

~~~ sql
> ADD TABLE vehicles VALIDATE CONSTRAINT fk_owner_id_ref_users;
~~~

~~~ sql
> ADD TABLE rides VALIDE CONSTRAINT fk_rider_id_ref_users;
~~~

~~~ sql
> ADD TABLE rides VALIDATE CONSTRAINT fk_vehicle_id_ref_vehicles;
~~~

## Step 4. Test read performance

### Primary key: Single-row result

Retrieving a single row base on the primary key will return in 2ms or less:

~~~ sql
> SELECT * FROM rides WHERE id = '000000a1-000c-4bcd-a6dd-fb943afb949d';
~~~

~~~
+--------------------------------------+--------------------------------------+--------------------------------------+---------------------------------+---------------------------+---------------------------------+----------------------------------+--------------------+
|                  id                  |               rider_id               |              vehicle_id              |          start_address          |        end_address        |           start_time            |             end_time             |      revenue       |
+--------------------------------------+--------------------------------------+--------------------------------------+---------------------------------+---------------------------+---------------------------------+----------------------------------+--------------------+
| 000000a1-000c-4bcd-a6dd-fb943afb949d | 372ac5f3-9055-4b67-9ec4-3678ed5485c9 | de806b23-0174-45f1-8c11-bcd19b6a6701 | 928 Charles Ranch               | 9516 Brianna Locks        | 2018-06-07 21:25:25.81953+00:00 | 2018-06-07 21:25:12.485589+00:00 | 25.494361937008918 |
|                                      |                                      |                                      |                                 |                           |                                 |                                  |                    |
|                                      |                                      |                                      | West Matthewfort, OH 32274-6966 | South Stephanie, SD 15602 |                                 |                                  |                    |
+--------------------------------------+--------------------------------------+--------------------------------------+---------------------------------+---------------------------+---------------------------------+----------------------------------+--------------------+
(1 row)

Time: 1.49999ms
~~~

Retrieving a subset of columns will be even faster:

~~~ sql
> SELECT vehicle_id, start_address, end_address
FROM rides
WHERE id = '000000a1-000c-4bcd-a6dd-fb943afb949d'
~~~

~~~
+--------------------------------------+---------------------------------+---------------------------+
|              vehicle_id              |          start_address          |        end_address        |
+--------------------------------------+---------------------------------+---------------------------+
| de806b23-0174-45f1-8c11-bcd19b6a6701 | 928 Charles Ranch               | 9516 Brianna Locks        |
|                                      |                                 |                           |
|                                      | West Matthewfort, OH 32274-6966 | South Stephanie, SD 15602 |
+--------------------------------------+---------------------------------+---------------------------+
(1 row)

Time: 1.092066ms
~~~

## Primary key: Multi-row result



## Secondary key: Single-result set

~~~ sql
> SELECT * FROM users WHERE name 'Amy Davila';
~~~

~~~
+--------------------------------------+------------+------------------------+------------------+
|                  id                  |    name    |        address         |   credit_card    |
+--------------------------------------+------------+------------------------+------------------+
| ffde50c8-921d-4e6c-8615-b1d35f8d87d7 | Amy Davila | 9783 Danielle Parks    | 6011956484788721 |
|                                      |            |                        |                  |
|                                      |            | Savannahtown, MO 48626 |                  |
+--------------------------------------+------------+------------------------+------------------+
(1 row)

Time: 218.072361ms
~~~

Check the query plan:

~~~ sql
> EXPLAIN SELECT * FROM users WHERE name 'Amy Davila';
~~~

~~~
+------+-------+---------------+
| Tree | Field |  Description  |
+------+-------+---------------+
| scan |       |               |
|      | table | users@primary |
|      | spans | ALL           |
+------+-------+---------------+
(3 rows)
~~~

Add a secondary index on `name`:

~~~ sql
> CREATE INDEX ON users (name);
~~~

After add a secondary index on `name`:

~~~ sql
> SELECT * FROM users WHERE name 'Amy Davila';
~~~

~~~
+--------------------------------------+------------+------------------------+------------------+
|                  id                  |    name    |        address         |   credit_card    |
+--------------------------------------+------------+------------------------+------------------+
| ffde50c8-921d-4e6c-8615-b1d35f8d87d7 | Amy Davila | 9783 Danielle Parks    | 6011956484788721 |
|                                      |            |                        |                  |
|                                      |            | Savannahtown, MO 48626 |                  |
+--------------------------------------+------------+------------------------+------------------+
(1 row)

Time: 2.47977ms
~~~

Check the improved query plan:

~~~ sql
> EXPLAIN SELECT * FROM users WHERE name 'Amy Davila';
~~~

~~~
+------------+-------+---------------------------------------+
|    Tree    | Field |              Description              |
+------------+-------+---------------------------------------+
| index-join |       |                                       |
|  ├── scan  |       |                                       |
|  │         | table | users@users_name_idx                  |
|  │         | spans | /"Amy Davila"-/"Amy Davila"/PrefixEnd |
|  └── scan  |       |                                       |
|            | table | users@primary                         |
+------------+-------+---------------------------------------+
(6 rows)
~~~

## Step 5. Tune read performance
