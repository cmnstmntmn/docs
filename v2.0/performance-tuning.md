---
title: Performance Tuning
summary: Essential techniques for getting fast reads and writes in a single- and multi-region CockroachDB deployment.
toc: true
---

This tutorial shows you essential techniques for getting fast reads and writes in CockroachDB, starting with a single-datacenter deployment and expanding into multiple regions.

{{site.data.alerts.callout_info}}
Note about how there other additional considerations for production deployments (clock synch, etc.). Reference Production Checklist and maybe the GCE tutorial.
{{site.data.alerts.end}}

## Overview

### Topology

You'll start with a 3-node CockroachDB cluster in a single Google Compute Engine (GCE) zone, with an extra instance for read/write testing:

<img src="{{ 'images/v2.0/perf_tuning_single_dc_topology.png' | relative_url }}" alt="Perf tuning topology" style="max-width:100%" />

{{site.data.alerts.callout_info}}
Within a single GCE zone, network latency between instances should be sub-millisecond.
{{site.data.alerts.end}}

You'll then scale the cluster to 9 nodes running across 3 GCE regions, with an extra instance in each region for read/write testing:

<img src="{{ 'images/v2.0/perf_tuning_single_dc_topology.png' | relative_url }}" alt="Perf tuning topology" style="max-width:100%" />

### Hardware

To reproduce the performance demonstrated in this tutorial:

- For CockroachDB nodes, you'll use [`n1-standard-4`](https://cloud.google.com/compute/docs/machine-types#standard_machine_types) instances (4 vCPUs, 15 GB memory) with [local SSDs](https://cloud.google.com/compute/docs/disks/#localssds).

- For read/write testing, you'll use smaller instances, such as `n1-standard-1`.

### Schema

You'll use sample schema and data for Cockroach Lab's fictional vehicle-sharing company, [MovR](https://github.com/cockroachdb/movr):

<img src="{{ 'images/v2.0/perf_tuning_single_dc_movr_schema.png' | relative_url }}" alt="Perf tuning schema" style="max-width:100%" />

{{site.data.alerts.callout_info}}
The [`IMPORT`](import.html) feature you'll use to import the data does not support foreign keys, so you'll import the data without the [foreign key constraints](foreign-key.html) but with the secondary indexes required to add the foreign key constraints after import.
{{site.data.alerts.end}}

### Important concepts

## Single-datacenter deployment

<!--
1. Reserve 4 VMs: roachprod create jesse-crdb -n 4
2. Put cockroach` on all VM: `roachprod run jesse-crdb "curl https://binaries.cockroachdb.com/cockroach-v2.0.3.linux-amd64.tgz | tar -xvz; mv cockroach-v2.0.3.linux-amd64/cockroach cockroach"
3. Start the cluster: roachprod start jesse-crdb:1-3
-->

### Step 1. Configure your network

CockroachDB requires TCP communication on two ports:

- **26257** (`tcp:26257`) for inter-node communication (i.e., working as a cluster)
- **8080** (`tcp:8080`) for accessing the Admin UI

Since GCE instances communicate on their internal IP addresses by default, you don't need to take any action to enable inter-node communication. However, if you want to access the Admin UI from your local network, you must [create a firewall rule for your project](https://cloud.google.com/vpc/docs/using-firewalls):

Field | Recommended Value
------|------------------
Name | **cockroachadmin**
Source filter | IP ranges
Source IP ranges | Your local network's IP ranges
Allowed protocols | **tcp:8080**
Target tags | `cockroachdb`

{{site.data.alerts.callout_info}}
The **tag** feature will let you easily apply the rule to your instances.
{{site.data.alerts.end}}

### Step 2. Create instances

1. [Create 3 instances](https://cloud.google.com/compute/docs/instances/create-start-instance) for your CockroachDB nodes. While creating each instance:  
    - Select the **us-east1-b** region.
    - Use the `n1-standard-4` machine type (4 vCPUs, 15 GB memory).
    - [Create and mount a local SSD](https://cloud.google.com/compute/docs/disks/local-ssd#create_local_ssd).
    - To apply the Admin UI firewall rule you created earlier, click **Management, disk, networking, SSH keys**, select the **Networking** tab, and then enter `cockroachdb` in the **Network tags** field.

2. Create a separate instance for read/write testing also in the **us-east1-b** region. This instance can be smaller, such as `n1-standard-1`.

### Step 3. Start a 3-node cluster

### Step 4. Import the Movr dataset

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

    {{site.data.alerts.callout_success}}
    You can observe the progress of imports as well as all schema change operations (e.g., adding secondary indexes) on the [**Jobs** page](admin-ui-jobs-page.html) of the Admin UI.
    {{site.data.alerts.end}}

7. Logically, there should be a number of [foreign key](foreign-key.html) relationships. As mentioned above, it wasn't possible to put these constraints in place during `IMPORT`, but it was possible to create the required secondary indexes. Now, let's add the foreign key constraints:

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

    **Add a note about why we need vehicle_city and link to ticket. Basically, we can't have 2 foreign keys constraints on the same column (city). So we duplicate city as vehicle_city and add check constraint to ensure that they are identical. https://github.com/cockroachdb/cockroach/issues/23580**

<!-- ## Step 4. Install the performance testing CLI

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

### Step 5. Tune read performance

{{site.data.alerts.callout_success}}
When reading from a table or index for the first time, the query will be slower than usual because the node issuing the query loads the schema of the table or index into memory first. For this reason, if you see an unusually slow query when first reading from a table, run the query a few more times to see more typical latencies.
{{site.data.alerts.end}}

#### Using the primary key

Retrieving a single row based on the primary key will almost always return in around 2ms:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM rides WHERE city = 'amsterdam' AND id = '000041ed-82d4-4d72-b822-fdb50ae49928';
~~~

~~~
+--------------------------------------+-----------+--------------+--------------------------------------+--------------------------------------+-------------------------------+------------------------------+----------------------------------+----------------------------------+---------+
|                  id                  |   city    | vehicle_city |               rider_id               |              vehicle_id              |         start_address         |         end_address          |            start_time            |             end_time             | revenue |
+--------------------------------------+-----------+--------------+--------------------------------------+--------------------------------------+-------------------------------+------------------------------+----------------------------------+----------------------------------+---------+
| 000041ed-82d4-4d72-b822-fdb50ae49928 | amsterdam | amsterdam    | ad8d4327-6f66-441a-b153-f9769b80bf63 | 29023f4a-0c23-4681-8d6d-ccff1b7520f2 | 024 Joseph Road               | 4730 Peterson Neck           | 2018-06-26 16:04:19.039034+00:00 | 2018-06-26 16:16:19.039034+00:00 |   55.28 |
|                                      |           |              |                                      |                                      |                               |                              |                                  |                                  |         |
|                                      |           |              |                                      |                                      | North Lindaton, NY 89020-0096 | Port Nicholas, NJ 16287-1322 |                                  |                                  |         |
+--------------------------------------+-----------+--------------+--------------------------------------+--------------------------------------+-------------------------------+------------------------------+----------------------------------+----------------------------------+---------+
(1 row)

Time: 2.392752ms
~~~

Retrieving a subset of columns will be even faster:

{% include copy-clipboard.html %}
~~~ sql
> SELECT vehicle_id, start_address, end_address
FROM rides
WHERE city = 'amsterdam' AND id = '000041ed-82d4-4d72-b822-fdb50ae49928';
~~~

~~~
+--------------------------------------+-------------------------------+------------------------------+
|              vehicle_id              |         start_address         |         end_address          |
+--------------------------------------+-------------------------------+------------------------------+
| 29023f4a-0c23-4681-8d6d-ccff1b7520f2 | 024 Joseph Road               | 4730 Peterson Neck           |
|                                      |                               |                              |
|                                      | North Lindaton, NY 89020-0096 | Port Nicholas, NJ 16287-1322 |
+--------------------------------------+-------------------------------+------------------------------+
(1 row)

Time: 1.949235ms
~~~

#### Using a full table scan

You'll get generally poor performance when retrieving a single row based on a column that is not in the primary key or any secondary index:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM users WHERE name = 'Casey Bell';
~~~

~~~
+--------------------------------------+-----------+------------+--------------------------+------------------+
|                  id                  |   city    |    name    |         address          |   credit_card    |
+--------------------------------------+-----------+------------+--------------------------+------------------+
| 011fefdc-5bf9-42df-9277-cc49bbae39ad | amsterdam | Casey Bell | 088 Tiffany Union        | 4924427245134960 |
|                                      |           |            |                          |                  |
|                                      |           |            | Lake Emilytown, MS 72223 |                  |
+--------------------------------------+-----------+------------+--------------------------+------------------+
(1 row)

Time: 5.108669ms
~~~

To understand why this query performs poorly, use [`EXPLAIN`](explain.html) to see the query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT * FROM users WHERE name = 'Casey Bell';
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

The row with `spans | ALL` shows you that, without a secondary index on the `name` column, CockroachDB scans every row of the `users` table, ordered by the primary key (`city`/`id`), until it finds the row with the correct `name` value.

#### Using a secondary index

To speed up this query, add a secondary index on `name`:

{% include copy-clipboard.html %}
~~~ sql
> CREATE INDEX on users (name);
~~~

The query will now return in 4ms or less:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM users WHERE name = 'Casey Bell';
~~~

~~~
+--------------------------------------+-----------+------------+--------------------------+------------------+
|                  id                  |   city    |    name    |         address          |   credit_card    |
+--------------------------------------+-----------+------------+--------------------------+------------------+
| 011fefdc-5bf9-42df-9277-cc49bbae39ad | amsterdam | Casey Bell | 088 Tiffany Union        | 4924427245134960 |
|                                      |           |            |                          |                  |
|                                      |           |            | Lake Emilytown, MS 72223 |                  |
+--------------------------------------+-----------+------------+--------------------------+------------------+
(1 row)

Time: 2.538495ms
~~~

To understand why performance has improved, use [`EXPLAIN`](explain.html) to see the new query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT * FROM users WHERE name = 'Casey Bell';
~~~

~~~
+------------+-------+---------------------------------------+
|    Tree    | Field |              Description              |
+------------+-------+---------------------------------------+
| index-join |       |                                       |
|  ├── scan  |       |                                       |
|  │         | table | users@users_name_idx                  |
|  │         | spans | /"Casey Bell"-/"Casey Bell"/PrefixEnd |
|  └── scan  |       |                                       |
|            | table | users@primary                         |
+------------+-------+---------------------------------------+
(6 rows)
~~~

This shows you that CockroachDB starts with the secondary index (`table | users@users_name_idx`). Because it is sorted by `name`, the query can jump directly to the relevant value (`spans | /"Casey Bell"-/"Casey Bell"/PrefixEnd`). However, the query needs to return values not in the secondary index, so CockroachDB grabs the primary key (`city`/`id`) stored with the `name` value (the primary key is always stored with entries in a secondary index), jumps to that value in the primary index, and then returns the full row.

#### Using a secondary index storing other columns

When you have a query that filters by a specific column but retrieves a subset of the table's total columns, you can improve performance by [storing](indexes.html#storing-columns) those additional columns in the secondary index to prevent the query from needing to scan the primary index as well.

For example, let's say you frequently retrieve a user's name and credit card number. As seen above, with the current secondary index on `name`, CockroachDB still needs to scan the primary index to get the credit card number:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT name, credit_card FROM users WHERE name = 'Casey Bell';
~~~

~~~
+-----------------+-------+---------------------------------------+
|      Tree       | Field |              Description              |
+-----------------+-------+---------------------------------------+
| render          |       |                                       |
|  └── index-join |       |                                       |
|       ├── scan  |       |                                       |
|       │         | table | users@users_name_idx                  |
|       │         | spans | /"Casey Bell"-/"Casey Bell"/PrefixEnd |
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
> EXPLAIN SELECT name, credit_card FROM users WHERE name = 'Casey Bell';
~~~

~~~
+-----------+-------+---------------------------------------+
|   Tree    | Field |              Description              |
+-----------+-------+---------------------------------------+
| render    |       |                                       |
|  └── scan |       |                                       |
|           | table | users@users_name_idx                  |
|           | spans | /"Casey Bell"-/"Casey Bell"/PrefixEnd |
+-----------+-------+---------------------------------------+
(4 rows)
~~~

This results in very fast performance, in this case under 2ms:

{% include copy-clipboard.html %}
~~~ sql
> SELECT name, credit_card FROM users WHERE name = 'Casey Bell';
~~~

~~~
+------------+------------------+
|    name    |   credit_card    |
+------------+------------------+
| Casey Bell | 4924427245134960 |
+------------+------------------+
(1 row)

Time: 1.99916ms
~~~

#### Using a cross-table join

Secondary indexes are crucial when [joining](joins.html) data from different tables as well.

For example, let's say you want to count the number of users who started rides within a given hour. To do this, you need to use a join to get the relevant rides from the `rides` table and then map the `rider_id` for each of those rides to the corresponding `id` in the `users` table, counting each mapping only once:

{% include copy-clipboard.html %}
~~~ sql
> SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-26 16:00:00' AND '2018-06-26 17:00:00';
~~~

~~~
+-------+
| count |
+-------+
|  1537 |
+-------+
(1 row)

Time: 746.251401ms
~~~

To understand what's happening, use [`EXPLAIN`](explain.html) to see the query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-26 16:00:00' AND '2018-06-26 17:00:00';
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

Time: 1.593771ms
~~~

Reading from bottom up, you can see that CockroachDB does a full table scan (`spans    | ALL`) first on `rides` to get all rows with a `start_time` in the specified range and then does another full table scan on `users` to find matching rows and calculate the count.

Given the `WHERE` condition, the full table scan of `rides` is particularly wasteful. To speed up the query, you can create a secondary index on the `WHERE` condition (`rides.start_time`) storing the join key (`rides.rider_id`) and then re-run the join:

{{site.data.alerts.callout_info}}
The `rides` table contains 1 million rows, so adding this index will take a few minutes.
{{site.data.alerts.end}}

{% include copy-clipboard.html %}
~~~ sql
> CREATE INDEX ON rides (start_time) STORING (rider_id);
~~~

{% include copy-clipboard.html %}
~~~ sql
> SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-26 16:00:00' AND '2018-06-26 17:00:00';
~~~

~~~
+-------+
| count |
+-------+
|  1537 |
+-------+
(1 row)

Time: 39.119995ms
~~~

Adding the secondary index reduced the query time from `746.251401ms` to `39.119995ms`.

To understand why performance has improved, again use [`EXPLAIN`](explain.html) to see the new query plan:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT count(DISTINCT users.id)
FROM users
INNER JOIN rides ON rides.rider_id = users.id
WHERE start_time BETWEEN '2018-06-26 16:00:00' AND '2018-06-26 17:00:00';
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
|                     | spans    | /2018-06-26T16:00:00Z-/2018-06-26T17:00:00.000000001Z |
+---------------------+----------+-------------------------------------------------------+
(11 rows)

Time: 1.521655ms
~~~

Notice that CockroachDB now starts by using `rides@rides_start_time_idx` secondary index to retrieve the relevant rides without needing to scan the full `rides` table.

#### Using `IN (list)`

For example, let's say you want to get the latest ride of each of the 5 most used vehicles. To do this, you might think to use a subquery to get the IDs of the 5 most frequent vehicles from the `rides` table, passing the results into the `IN` list of another query to get the most recent ride of each of the 5 vehicles:

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
| 7193da42-1aea-43ec-a4a9-02411b5c1f4e | 2018-07-12 16:50:57.171841+00:00 |
| 7e2c4757-149c-4d41-bd0f-59fc7c8cc6c8 | 2018-07-12 16:51:52.11815+00:00  |
| e1801dda-f8f5-4571-9379-023206697e63 | 2018-07-12 17:31:31.111566+00:00 |
| a92deee5-7df2-45a5-a558-58799921e862 | 2018-07-12 16:28:54.957921+00:00 |
| a24102db-9f93-48a4-9493-56167d25be1c | 2018-07-12 16:32:21.469963+00:00 |
+--------------------------------------+----------------------------------+
(5 rows)

Time: 4.192479105s
~~~

However, as you can see, this query is slow because, currently, when the `WHERE` condition of a query comes from the result of a subquery, CockroachDB scans the entire table, even if there is an available index. Use `EXPLAIN` to see this in more detail:

{% include copy-clipboard.html %}
~~~ sql
> EXPLAIN SELECT vehicle_id, max(end_time)
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

Time: 2.192193ms
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
| a92deee5-7df2-45a5-a558-58799921e862 |
| 7e2c4757-149c-4d41-bd0f-59fc7c8cc6c8 |
| a24102db-9f93-48a4-9493-56167d25be1c |
| 7193da42-1aea-43ec-a4a9-02411b5c1f4e |
| e1801dda-f8f5-4571-9379-023206697e63 |
+--------------------------------------+
(5 rows)

Time: 723.73484ms
~~~

And then put the results into the `IN` list of the query to get the most recent rides of the vehicles:

{% include copy-clipboard.html %}
~~~ sql
> SELECT vehicle_id, max(end_time)
FROM rides
WHERE vehicle_id IN (
  'a92deee5-7df2-45a5-a558-58799921e862',
  '7e2c4757-149c-4d41-bd0f-59fc7c8cc6c8',
  'a24102db-9f93-48a4-9493-56167d25be1c',
  '7193da42-1aea-43ec-a4a9-02411b5c1f4e',
  'e1801dda-f8f5-4571-9379-023206697e63'
)
GROUP BY vehicle_id;
~~~

~~~
+--------------------------------------+----------------------------------+
|              vehicle_id              |               max                |
+--------------------------------------+----------------------------------+
| a24102db-9f93-48a4-9493-56167d25be1c | 2018-07-12 16:32:21.469963+00:00 |
| 7e2c4757-149c-4d41-bd0f-59fc7c8cc6c8 | 2018-07-12 16:51:52.11815+00:00  |
| e1801dda-f8f5-4571-9379-023206697e63 | 2018-07-12 17:31:31.111566+00:00 |
| 7193da42-1aea-43ec-a4a9-02411b5c1f4e | 2018-07-12 16:50:57.171841+00:00 |
| a92deee5-7df2-45a5-a558-58799921e862 | 2018-07-12 16:28:54.957921+00:00 |
+--------------------------------------+----------------------------------+
(5 rows)

Time: 819.366599ms
~~~

This approach reduced the query time from `4.192479105s` (query with subquery) to `1.543101439s` (2 distinct queries).

### Step 6. Tune write performance

#### Bulk inserts into an existing table

{% include copy-clipboard.html %}
~~~ sql
> INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347');
INSERT INTO users VALUES (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347');
~~~

{% include copy-clipboard.html %}
~~~ sql
> INSERT INTO users VALUES
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Frank Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Susie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Chris Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Jer Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Karen Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marc Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Layla Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Francine Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'William Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Leslie Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Max Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Bob Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Tanya Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Rebecca Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Louis Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Abe Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Marsha Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Fred Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Barry Roach', '411 Drum Street', '173635282937347'),
    (gen_random_uuid(), 'new york', 'Maxine Roach', '411 Drum Street', '173635282937347')
;
~~~

Next:

- minimizing indexes (could drop fks just to show the cost of fks)
- upsert instead of insert/update
- update using case expressions (instead of 2 separate updates)
- returning nothing
- insert with returning (auto gen ID) instead of select to get auto gen ID
- Maybe interleaved tables

## Multi-region deployment

### Step 7. Create more instances

### Step 8. Scale to 9 nodes across 3 regions

### Step 9. Test performance before partitioning

### Step 10. Partition your data by city

### Step 11. Test performance after partitioning
