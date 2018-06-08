---
title: Performance Tuning
summary: Essential techniques for getting fast reads and writes in a single- and multi-datacenter CockroachDB deployment.
toc: true
---

This tutorial shows you essential techniques for getting fast reads and writes in CockroachDB, starting in a single datacenter and growing into a multi-datacenter deployment.

## Overview

### Schema

You'll use sample schema and data for Cockroach Lab's fictional vehicle-sharing company, [MovR](https://github.com/cockroachdb/movr):

<img src="{{ 'images/v2.0/perf_tuning_single_dc_movr_schema.png' | relative_url }}" alt="Perf tuning schema" style="max-width:100%" />

{{site.data.alerts.callout_info}}
The [`IMPORT`](import.html) feature you'll use to import the data does not support foreign keys, so you'll import the data without the [foreign key constraints](foreign-key.html) but with the secondary indexes required to add the foreign key constraints after import.
{{site.data.alerts.end}}

### Topology

To reproduce the performance demonstrated in this tutorial, you'll use the following topology:

- A 3-node CockroachDB cluster in a single Google Cloud Platform GCE datacenter, each node running on an [`n1-standard-4`](https://cloud.google.com/compute/docs/machine-types#standard_machine_types) VM (4 virtual CPUs, 15 GB of memory) with [local SSD storage](https://cloud.google.com/compute/docs/disks/#localssds).
- A fourth smaller VM in the same datacenter for read/write testing.

<img src="{{ 'images/v2.0/perf_tuning_single_dc_topology.png' | relative_url }}" alt="Perf tuning topology" style="max-width:100%" />

{{site.data.alerts.callout_info}}
Within a single GCE datacenter, network latency between VMs should be sub-millisecond.
{{site.data.alerts.end}}

### Important concepts

## Single-datacenter deployment

### Step 1. Start a 3-node cluster

Follow steps 1-6 of the [GCE tutorial](deploy-cockroachdb-on-google-cloud-platform-insecure.html) to deploy a 3-node CockroachDB cluster on Google Cloud Platform GCE.

- For the 3 CockroachDB nodes, use [`n1-standard-4`](https://cloud.google.com/compute/docs/machine-types#standard_machine_types) VMs with [local SSD storage](https://cloud.google.com/compute/docs/disks/local-ssd#create_local_ssd).
- Reserve a fourth VM for read and write testing. This VM can be smaller.
- Make sure all VMs are within the same datacenter.
- Skip step 4, for setting up Google's manage load balancing service (you won't need load balancing for this tutorial).

<!--
1. Reserve 4 VMs: roachprod create jesse-crdb -n 4
2. Put cockroach` on all VM: `roachprod run jesse-crdb "curl https://binaries.cockroachdb.com/cockroach-v2.0.3.linux-amd64.tgz | tar -xvz; mv cockroach-v2.0.3.linux-amd64/cockroach cockroach"
3. Start the cluster: roachprod start jesse-crdb:1-3
-->

<!-- ## Step 2. Start a load balancer

[HAProxy](http://www.haproxy.org/) is one of the most popular open-source TCP load balancers, and CockroachDB includes a built-in command for generating a configuration file that is preset to work with your running cluster, so we feature that tool here.

1. Create a fourth VM for load balancing and read and write testing.

2. SSH to the fourth VM.

3. Make sure all of the system software is up-to-date:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ sudo apt-get update && sudo apt-get -y upgrade
    ~~~

4. Install HAProxy:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ apt-get install haproxy
	  ~~~

5. Download the [CockroachDB archive](https://binaries.cockroachdb.com/cockroach-{{ page.release_info.version }}.linux-amd64.tgz) for Linux, and extract the binary:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ wget -qO- https://binaries.cockroachdb.com/cockroach-{{ page.release_info.version }}.linux-amd64.tgz \
    | tar  xvz
    ~~~

6. Copy the binary into the `PATH`:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ cp -i cockroach-{{ page.release_info.version }}.linux-amd64/cockroach /usr/local/bin
    ~~~

	If you get a permissions error, prefix the command with `sudo`.

7. Run the [`cockroach gen haproxy`](generate-cockroachdb-resources.html) command, specifying the address of any CockroachDB node:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ cockroach gen haproxy --insecure \
    --host=<address of any node> \
    --port=26257
    ~~~

    By default, the generated configuration file is called `haproxy.cfg` and looks as follows, with the `server` addresses pre-populated correctly:

    ~~~
    global
      maxconn 4096

    defaults
        mode                tcp
        # Timeout values should be configured for your specific use.
        # See: https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#4-timeout%20connect
        timeout connect     10s
        timeout client      1m
        timeout server      1m
        # TCP keep-alive on client side. Server already enables them.
        option              clitcpka

    listen psql
        bind :26257
        mode tcp
        balance roundrobin
        option httpchk GET /health?ready=1
        server cockroach1 <node1 address>:26257 check port 8080
        server cockroach2 <node2 address>:26257 check port 8080
        server cockroach3 <node3 address>:26257 check port 8080
    ~~~

  	The file is preset with the minimal [configurations](http://cbonte.github.io/haproxy-dconv/1.7/configuration.html) needed to work with your running cluster:

  	Field | Description
  	------|------------
  	`timeout connect`<br>`timeout client`<br>`timeout server` | Timeout values that should be suitable for most deployments.
  	`bind` | The port that HAProxy listens on. This is the port clients will connect to and thus needs to be allowed by your network configuration.<br><br>This tutorial assumes HAProxy is running on a separate machine from CockroachDB nodes. If you run HAProxy on the same machine as a node (not recommended), you'll need to change this port, as `26257` is likely already being used by the CockroachDB node.
  	`balance` | The balancing algorithm. This is set to `roundrobin` to ensure that connections get rotated amongst nodes (connection 1 on node 1, connection 2 on node 2, etc.). Check the [HAProxy Configuration Manual](http://cbonte.github.io/haproxy-dconv/1.7/configuration.html#4-balance) for details about this and other balancing algorithms.
    `option httpchk` | The HTTP endpoint that HAProxy uses to check node health. [`/health?ready=1`](monitoring-and-alerting.html#health-ready-1) ensures that HAProxy doesn't direct traffic to nodes that are live but not ready to receive requests.
    `server` | For each node in the cluster, this field specifies the interface that the node listens on (i.e., the address passed in the `--host` flag on node startup) as well as the port to use for HTTP health checks.

  	{{site.data.alerts.callout_info}}For full details on these and other configuration settings, see the <a href="http://cbonte.github.io/haproxy-dconv/1.7/configuration.html">HAProxy Configuration Manual</a>.{{site.data.alerts.end}}

8. Start HAProxy, with the `-f` flag pointing to the `haproxy.cfg` file:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ haproxy -f haproxy.cfg &
    ~~~ -->

### Step 2. Import the `movr` database

<!--
roachprod list -d jesse-crdb
roachprod run jesse-crdb:4
./cockroach sql --insecure --host=<any node>
-->

1. SSH to the fourth VM, the one not running a CockroachDB node.

2. Download the [CockroachDB archive](https://binaries.cockroachdb.com/cockroach-{{ page.release_info.version }}.linux-amd64.tgz) for Linux, and extract the binary:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ wget -qO- https://binaries.cockroachdb.com/cockroach-{{ page.release_info.version }}.linux-amd64.tgz \
    | tar  xvz
    ~~~

3. Copy the binary into the `PATH`:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ cp -i cockroach-{{ page.release_info.version }}.linux-amd64/cockroach /usr/local/bin
    ~~~

    If you get a permissions error, prefix the command with `sudo`.

4. Start the [built-in SQL shell](use-the-built-in-sql-client.html), pointing it one of the CockroachDB nodes:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ cockroach sql --insecure --host=<address of any node>
    ~~~

5. Create the `movr` database and set it as the default:

    {% include copy-clipboard.html %}
    ~~~ sql
    > CREATE DATABASE movr;
    ~~~

    {% include copy-clipboard.html %}
    ~~~ sql
    > SET DATABASE = movr;
    ~~~

6. Use the [`IMPORT`](import.html) statement to create and populate the `users`, `vehicles,` and `rides` tables:

    {% include copy-clipboard.html %}
    ~~~ sql
    > IMPORT TABLE users (
      	id UUID NOT NULL,
        city STRING NOT NULL,
      	name STRING NULL,
      	address STRING NULL,
      	credit_card STRING NULL,
        CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC)
    )
    CSV DATA (
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/users/n1.0.csv'
    );
    ~~~

    ~~~
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    |       job_id       |  status   | fraction_completed | rows | index_entries | system_records | bytes |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    | 364858539979014145 | succeeded |                  1 |    0 |             0 |              0 |     0 |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    (1 row)

    Time: 2.91178647s
    ~~~    

    <!-- ~~~ sql
    > IMPORT TABLE users (
      	id UUID NOT NULL PRIMARY KEY,
      	name STRING NULL,
      	address STRING NULL,
      	credit_card STRING NULL
    )
    CSV DATA (
        's3://cockroachdb-movr/datasets/large-csv/users/n1.0.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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',
        's3://cockroachdb-movr/datasets/large-csv/users/n1.1.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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'
    );
    ~~~ -->

    {% include copy-clipboard.html %}
    ~~~ sql
    > IMPORT TABLE vehicles (
      	id UUID NOT NULL,
        city STRING NOT NULL,
      	type STRING NULL,
      	owner_id UUID NULL,
      	creation_time TIMESTAMP NULL,
      	status STRING NULL,
        mycol STRING NULL,
      	ext JSON NULL,
        CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),
        INDEX vehicles_auto_index_fk_city_ref_users (city ASC, owner_id ASC)
    )
    CSV DATA (
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/vehicles/n1.0.csv'
    );
    ~~~

    ~~~
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    |       job_id       |  status   | fraction_completed | rows | index_entries | system_records | bytes |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    | 364860420800708609 | succeeded |                  1 |    0 |             0 |              0 |     0 |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    (1 row)

    Time: 6.791710165s
    ~~~

    <!-- {% include copy-clipboard.html %}
    ~~~ sql
    > IMPORT TABLE vehicles (
      	id UUID NOT NULL PRIMARY KEY,
      	type STRING NULL,
      	city STRING NOT NULL,
      	owner_id UUID NULL,
      	creation_time TIMESTAMP NULL,
      	status STRING NULL,
      	ext JSON NULL,
        INDEX vehicles_owner_id_idx (owner_id ASC)
    )
    CSV DATA (
        's3://cockroachdb-movr/datasets/large-csv/vehicles/n1.0.csv?AWS_ACCESS_KEY_ID=AKIAIEQAQEMX2GD4YEKQ&AWS_SECRET_ACCESS_KEY=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'
    );
    ~~~ -->

    {% include copy-clipboard.html %}
    ~~~ sql
    > IMPORT TABLE rides (
      	id UUID NOT NULL,
        city STRING NOT NULL,
        vehicle_city STRING NULL,
      	rider_id UUID NULL,
      	vehicle_id UUID NULL,
      	start_address STRING NULL,
      	end_address STRING NULL,
      	start_time TIMESTAMP NULL,
      	end_time TIMESTAMP NULL,
      	revenue DECIMAL(10,2) NULL,
        CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),
        INDEX rides_auto_index_fk_city_ref_users (city ASC, rider_id ASC),
        INDEX rides_auto_index_fk_vehicle_city_ref_vehicles (vehicle_city ASC, vehicle_id ASC),
        CONSTRAINT check_vehicle_city_city CHECK (vehicle_city = city)
    )
    CSV DATA (
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.0.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.1.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.2.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.3.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.4.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.5.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.6.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.7.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.8.csv',
        'https://s3-us-west-1.amazonaws.com/cockroachdb-movr/datasets/perf-tuning/rides/n1.9.csv'
    );
    ~~~

    ~~~
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    |       job_id       |  status   | fraction_completed | rows | index_entries | system_records | bytes |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    | 364861341888217089 | succeeded |                  1 |    0 |             0 |              0 |     0 |
    +--------------------+-----------+--------------------+------+---------------+----------------+-------+
    (1 row)

    Time: 49.622076145s
    ~~~

    <!-- {% include copy-clipboard.html %}
    ~~~ sql
    > IMPORT TABLE rides (
      	id UUID NOT NULL PRIMARY KEY,
      	rider_id UUID NULL,
      	vehicle_id UUID NULL,
      	start_address STRING NULL,
      	end_address STRING NULL,
      	start_time TIMESTAMP NULL,
      	end_time TIMESTAMP NULL,
      	revenue FLOAT NULL,
        INDEX rides_rider_id_idx (rider_id ASC),
        INDEX rides_vehicle_id_idx (vehicle_id ASC)
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
    ~~~ -->

    {{site.data.alerts.callout_success}}
    You can observe the progress of imports as well as all schema change operations (e.g., adding secondary indexes) on the [**Jobs** page](admin-ui-jobs-page.html) of the Admin UI.
    {{site.data.alerts.end}}

7. Logically, there should be a number of [foreign key](foreign-key.html) relationships. As mentioned above, during `IMPORT`, it wasn't possible to put these constraints in place, but it was possible to create the required secondary indexes. Now, let's add the foreign key constraints:

    {% include copy-clipboard.html %}
    ~~~ sql
    > ALTER TABLE vehicles
    ADD CONSTRAINT fk_city_ref_users
    FOREIGN KEY (city, owner_id)
    REFERENCES users (city, id);
    ~~~

    {% include copy-clipboard.html %}
    ~~~ sql
    > ALTER TABLE rides
    ADD CONSTRAINT fk_city_ref_users
    FOREIGN KEY (city, rider_id)
    REFERENCES users (city, id);
    ~~~

    {% include copy-clipboard.html %}
    ~~~ sql
    > ALTER TABLE rides
    ADD CONSTRAINT fk_vehicle_city_ref_vehicles
    FOREIGN KEY (vehicle_city, vehicle_id)
    REFERENCES vehicles (city, id);
    ~~~

<!-- 8. Use `\q` or **CTRL-C** to exit the SQL shell.

## Step 4. Install the performance testing CLI

You'll use a command-line utility written in Python to create connections and issue queries to the cluster.

1. Still on the fourth VM, install Pip:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ sudo apt-get install python-pip
    ~~~

2. Use Pip to install the `psycopg2` driver:

    {% include copy-clipboard.html %}
    ~~~ shell
    $ pip install psycopg2-binary
    ~~~

3. Download the `performance-tuning.py` file, or create the file yourself and copy the code into it:

{% include copy-clipboard.html %}
~~~ python
{% include performance-tuning.py %}
~~~   -->

### Step 3. Test and tune read performance

{{site.data.alerts.callout_success}}
When reading from a table or index for the first time, the query will be slower than usual because the node issuing the query loads the schema of the table or index into memory first. For this reason, if you see an unusually slow query when first reading from a table, run the query a few more times to see more typical latencies.
{{site.data.alerts.end}}

#### Using the primary key

Retrieving a single row based on the primary key will almost always return in around 2ms:

{% include copy-clipboard.html %}
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

Time: 1.635518ms
~~~

Retrieving a subset of columns will be even faster:

{% include copy-clipboard.html %}
~~~ sql
> SELECT vehicle_id, start_address, end_address
FROM rides
WHERE id = '000000a1-000c-4bcd-a6dd-fb943afb949d';
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

Time: 1.275687ms
~~~

#### Using a full table scan

You'll get generally poor performance when retrieving a single row based on a column that is not in the primary key or any secondary index:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM users WHERE name = 'Amy Davila';
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

Time: 265.557691ms
~~~

To understand why this query performs poorly, use [`EXPLAIN`](explain.html) to see the query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT * FROM users WHERE name = 'Amy Davila';
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

The row with `spans | ALL` shows you that, without a secondary index on the `name` column, CockroachDB scans every row of the `users` table, ordered by the primary key (`id`), until it finds the row with the correct `name` value.

#### Using a secondary index

To speed up this query, add a secondary index on `name`:

{% include copy-clipboard.html %}
~~~ sql
> CREATE INDEX on users (name);
~~~

The query will now return in 4ms or less:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM users WHERE name = 'Amy Davila';
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

Time: 2.955016ms
~~~

To understand why performance has improved, use [`EXPLAIN`](explain.html) to see the new query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT * FROM users WHERE name = 'Amy Davila';
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

This shows you that CockroachDB starts with the secondary index (`table | users@users_name_idx`). Because it is sorted by `name`, the query can jump directly to the relevant value (`spans | /"Amy Davila"-/"Amy Davila"/PrefixEnd`). However, the query needs to return values not in the secondary index, so CockroachDB grabs the `id` stored with the `name` value (the primary key is always stored with entries in a secondary index), jumps to that `id` value in the primary index, and then returns the full row.

#### Using a secondary index storing other columns

When you have a query that filters by a specific column but retrieves a subset of the table's total columns, you can improve performance by [storing](indexes.html#storing-columns) those additional columns in the secondary index to prevent the query from needing to scan the primary index as well.

For example, let's say you frequently retrieve a user's name and credit card number. As seen above, with the current secondary index on `name`, CockroachDB still needs to scan the primary index to get the credit card number:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT name, credit_card FROM users WHERE name = 'Amy Davila';
~~~

~~~
+-----------------+-------+---------------------------------------+
|      Tree       | Field |              Description              |
+-----------------+-------+---------------------------------------+
| render          |       |                                       |
|  └── index-join |       |                                       |
|       ├── scan  |       |                                       |
|       │         | table | users@users_name_idx                  |
|       │         | spans | /"Amy Davila"-/"Amy Davila"/PrefixEnd |
|       └── scan  |       |                                       |
|                 | table | users@primary                         |
+-----------------+-------+---------------------------------------+
(7 rows)
~~~

Let's drop and recreate the index on `name`, this time storing the `credit_card` value in the index:

{% include copy-clipboard.html %}
~~~ sql
> DROP INDEX users_name_idx;
~~~

{% include copy-clipboard.html %}
~~~ sql
> CREATE INDEX on users (name) STORING (credit_card);
~~~

Now that `credit_card` values are stored in the index on `name`, CockroachDB only needs to scan that index:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT name, credit_card FROM users WHERE name = 'Amy Davila';
~~~

~~~
+-----------+-------+---------------------------------------+
|   Tree    | Field |              Description              |
+-----------+-------+---------------------------------------+
| render    |       |                                       |
|  └── scan |       |                                       |
|           | table | users@users_name_idx                  |
|           | spans | /"Amy Davila"-/"Amy Davila"/PrefixEnd |
+-----------+-------+---------------------------------------+
(4 rows)
~~~

This results in very fast performance, in this case under 2ms:

{% include copy-clipboard.html %}
~~~ sql
> SELECT name, credit_card FROM users WHERE name = 'Amy Davila';
~~~

~~~
+------------+------------------+
|    name    |   credit_card    |
+------------+------------------+
| Amy Davila | 6011956484788721 |
+------------+------------------+
(1 row)

Time: 1.909258ms
~~~

#### Using a cross-table join

Secondary indexes are crucial when [joining](joins.html) data from different tables as well.

For example, let's say you want to count the number of users who started rides in a 2-minute period. To do this, you need to use a join to get the relevant rides from the `rides` table and then map the `rider_id` for each of those rides to the corresponding `id` in the `users` table, counting each mapping only once:

{% include copy-clipboard.html %}
~~~ sql
> SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-07 20:30:00' AND '2018-06-07 20:32:00';
~~~

~~~
+-------+
| count |
+-------+
|  9762 |
+-------+
(1 row)

Time: 1.139548258s
~~~

To understand what's happening, use [`EXPLAIN`](explain.html) to see the query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE rides.start_time BETWEEN '2018-06-07 20:30:00' AND '2018-06-07 20:32:00';
~~~

~~~
+---------------------+----------+-------------------+
|        Tree         |  Field   |    Description    |
+---------------------+----------+-------------------+
| group               |          |                   |
|  └── render         |          |                   |
|       └── join      |          |                   |
|            │        | type     | inner             |
|            │        | equality | (id) = (rider_id) |
|            ├── scan |          |                   |
|            │        | table    | users@primary     |
|            │        | spans    | ALL               |
|            └── scan |          |                   |
|                     | table    | rides@primary     |
|                     | spans    | ALL               |
+---------------------+----------+-------------------+
(11 rows)

Time: 1.908609ms
~~~

Reading from bottom up, you can see that CockroachDB does a full table scan (`spans    | ALL`) first on `rides` to get all rows with a `start_time` in the specified range and then does another full table scan on `users` to find matching rows and calculate the count.

Given the `WHERE` condition, the full table scan of `rides` is particularly wasteful. To speed up the query, you can create a secondary index on the `WHERE` condition (`rides.start_time`) storing the join key (`rides.rider_id`) and then re-run the join:

{% include copy-clipboard.html %}
~~~ sql
> CREATE INDEX ON rides (start_time) STORING (rider_id);
~~~

{% include copy-clipboard.html %}
~~~ sql
> SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-07 20:30:00' AND '2018-06-07 20:32:00';
~~~

~~~
+-------+
| count |
+-------+
|  9762 |
+-------+
(1 row)

Time: 254.443247ms
~~~

Adding the secondary index reduced the query time from `1.139548258s` to `254.443247ms`.

To understand why performance has improved, again use [`EXPLAIN`](explain.html) to see the new query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE rides.start_time BETWEEN '2018-06-07 20:30:00' AND '2018-06-07 20:32:00';
~~~

~~~
+---------------------+----------+-------------------------------------------------------+
|        Tree         |  Field   |                      Description                      |
+---------------------+----------+-------------------------------------------------------+
| group               |          |                                                       |
|  └── render         |          |                                                       |
|       └── join      |          |                                                       |
|            │        | type     | inner                                                 |
|            │        | equality | (id) = (rider_id)                                     |
|            ├── scan |          |                                                       |
|            │        | table    | users@primary                                         |
|            │        | spans    | ALL                                                   |
|            └── scan |          |                                                       |
|                     | table    | rides@rides_start_time_idx                            |
|                     | spans    | /2018-06-07T20:30:00Z-/2018-06-07T20:32:00.000000001Z |
+---------------------+----------+-------------------------------------------------------+
(11 rows)

Time: 1.625745ms
~~~

Notice that CockroachDB now starts by using `rides@rides_start_time_idx` secondary index to retrieve the relevant rides without needing to scan the full `rides` table.

#### Using `IN (list)`

Currently, when the `WHERE` condition of a query comes from the result of a subquery, CockroachDB will scan the entire table, even if there is an available index.

For example, let's say you want to get the latest ride of each of the 5 most used vehicles. To do this, you can use a subquery to get the IDs of the 5 most frequent vehicles from the `rides` table, passing the results into the `IN` list of another query to get the most recent ride of each of the 5 vehicles:

{% include copy-clipboard.html %}
~~~ sql
SELECT vehicle_id, max(end_time)
FROM rides
WHERE vehicle_id IN (
    SELECT vehicle_id
    FROM rides
    GROUP BY vehicle_id
    ORDER BY count(*) DESC
    LIMIT 5
)
GROUP BY vehicle_id;
~~~

~~~
+--------------------------------------+----------------------------------+
|              vehicle_id              |               max                |
+--------------------------------------+----------------------------------+
| eb6cd460-54c1-42a8-9b52-96e5ff56ff53 | 2018-06-07 21:52:42.804861+00:00 |
| 2c3525d6-922d-4fb2-89e0-fba22eca0742 | 2018-06-07 21:51:03.888417+00:00 |
| a6e60590-b827-4e2b-b0b6-aa6dd6e37f73 | 2018-06-07 21:48:34.694626+00:00 |
| 4114333d-14dc-47b1-b745-ea7fea27574d | 2018-06-07 21:46:20.451079+00:00 |
| 13aea20a-d552-460a-b448-a045fa7a5bda | 2018-06-07 21:46:29.700447+00:00 |
+--------------------------------------+----------------------------------+
(5 rows)

Time: 5.101302147s
~~~

This query is slow for the reason mentioned above. Use `EXPLAIN` to understand this in more detail:

{% include copy-clipboard.html %}
~~~ sql
EXPLAIN SELECT vehicle_id, max(end_time)
FROM rides
WHERE vehicle_id IN (
    SELECT vehicle_id
    FROM rides
    GROUP BY vehicle_id
    ORDER BY count(*) DESC
    LIMIT 5
)
GROUP BY vehicle_id;
~~~

~~~
+------------------------------------+-----------+--------------------------------------------------------------------------+
|                Tree                |   Field   |                               Description                                |
+------------------------------------+-----------+--------------------------------------------------------------------------+
| root                               |           |                                                                          |
|  ├── group                         |           |                                                                          |
|  │    │                            | group by  | @1-@1                                                                    |
|  │    └── render                   |           |                                                                          |
|  │         └── scan                |           |                                                                          |
|  │                                 | table     | rides@primary                                                            |
|  │                                 | spans     | ALL                                                                      |
|  └── subquery                      |           |                                                                          |
|       │                            | id        | @S1                                                                      |
|       │                            | sql       | (SELECT vehicle_id FROM rides GROUP BY vehicle_id ORDER BY count(*) DESC |
|                                    |           | LIMIT 5)                                                                 |
|       │                            | exec mode | all rows normalized                                                      |
|       └── limit                    |           |                                                                          |
|            └── sort                |           |                                                                          |
|                 │                  | order     | -count                                                                   |
|                 │                  | strategy  | top 5                                                                    |
|                 └── group          |           |                                                                          |
|                      │             | group by  | @1-@1                                                                    |
|                      └── render    |           |                                                                          |
|                           └── scan |           |                                                                          |
|                                    | table     | rides@primary                                                            |
|                                    | spans     | ALL                                                                      |
+------------------------------------+-----------+--------------------------------------------------------------------------+
(21 rows)

Time: 1.229569ms
~~~

The important thing to notice is the full table scan of `rides@primary` above the `subquery`. This shows you that, after the subquery returns the IDs of the top 5 vehicles, CockroachDB scans the entire primary index to find the rows with `max(end_time)` for each `vehicle_id`, although you might expect CockroachDB to more efficiently use the secondary index on `vehicle_id`.

Because CockroachDB won't use an available secondary index in this case, it's much more performant to have your application first select the top 5 vehicles:

{% include copy-clipboard.html %}
~~~ sql
> SELECT vehicle_id
FROM rides
GROUP BY vehicle_id
ORDER BY count(*) DESC
LIMIT 5;
~~~

~~~
+--------------------------------------+
|              vehicle_id              |
+--------------------------------------+
| a6e60590-b827-4e2b-b0b6-aa6dd6e37f73 |
| eb6cd460-54c1-42a8-9b52-96e5ff56ff53 |
| 13aea20a-d552-460a-b448-a045fa7a5bda |
| b6742822-12b9-42c8-89f9-5885c551bc36 |
| 2c3525d6-922d-4fb2-89e0-fba22eca0742 |
+--------------------------------------+
(5 rows)

Time: 937.326892ms
~~~

And then put the results into the `IN` list of the query to get the most recent rides of the vehicles:

{% include copy-clipboard.html %}
~~~ sql
> SELECT vehicle_id, max(end_time)
FROM rides
WHERE vehicle_id IN (
  '20b4f7db-ac2e-41ea-bad1-90f64ac7de02',
  'f1ad5500-b49a-4f7d-bd21-7aa1864287cc',
  'eb6cd460-54c1-42a8-9b52-96e5ff56ff53',
  '13aea20a-d552-460a-b448-a045fa7a5bda',
  'a6e60590-b827-4e2b-b0b6-aa6dd6e37f73'
)
GROUP BY vehicle_id;
~~~

~~~
+--------------------------------------+----------------------------------+
|              vehicle_id              |               max                |
+--------------------------------------+----------------------------------+
| eb6cd460-54c1-42a8-9b52-96e5ff56ff53 | 2018-06-07 21:52:42.804861+00:00 |
| 13aea20a-d552-460a-b448-a045fa7a5bda | 2018-06-07 21:46:29.700447+00:00 |
| f1ad5500-b49a-4f7d-bd21-7aa1864287cc | 2018-06-07 21:46:13.421981+00:00 |
| a6e60590-b827-4e2b-b0b6-aa6dd6e37f73 | 2018-06-07 21:48:34.694626+00:00 |
| 20b4f7db-ac2e-41ea-bad1-90f64ac7de02 | 2018-06-07 21:52:30.195992+00:00 |
+--------------------------------------+----------------------------------+
(5 rows)

Time: 7.295667ms
~~~

This approach reduced the query time from `5.101302147s` to `944.622559ms`.

### Step 4. Test and tune write performance

#### Bulk inserts into an existing table

{% include copy-clipboard.html %}
~~~ sql
> INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347');
~~~

{% include copy-clipboard.html %}
~~~ sql
> INSERT INTO users VALUES
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'Maxine Roach', '411 Drum Street', '173635282937347')
;
~~~

## Multi-datacenter deployment

### Step 5. Scale to 9 nodes across 3 datacenters

### Step 6. Test performance before partitioning

### Step 7. Partition the data by city

### Step 8. Test performance after partitioning
