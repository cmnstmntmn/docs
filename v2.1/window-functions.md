---
title: WINDOW FUNCTIONS
summary: A window function performs a calculation across a set of table rows that are somehow related to the current row.
toc: true
---

CockroachDB supports the application of a function over a subset of the rows returned by a [selection query][selection-query].  Such a function is known as a _window function_, and it allows you to compute values by operating on more than one row at a time.  The subset of rows a window function operates on is known as a _window frame_.

{{site.data.alerts.callout_info}}
Most aggregate functions can also be used as window functions.  For more information, see the [Examples](#examples) below.
{{site.data.alerts.end}}

## How window functions work

At a high level, window functions work by:

1. Creating a "virtual table" using an outer [selection query][selection-query].
2. Splitting that table into window frames using an `OVER (PARTITION BY ...)` clause.
3. Applying the window function to each of the window frames created in step 2

For example, given the query

{% include copy-clipboard.html %}
~~~ sql
SELECT DISTINCT(city),
            SUM(revenue) OVER (PARTITION BY city) AS city_revenue
           FROM rides
       ORDER BY city_revenue DESC;
~~~

its operation can be described as follows (numbered steps listed here correspond to the numbers in the diagram below):

1. The outer `SELECT DISTINCT(city) ... FROM rides` creates a "virtual table" on which the window functions will operate
2. The window function `SUM(revenue) OVER ()` operates on a window frame containing all rows of the query output.
3. The window function `SUM(revenue) OVER (PARTITION BY city)` operates on several window frames in turn; each frame contains the `revenue` columns for a different city (Amsterdam, Boston, L.A., etc.).

<img src="{{ 'images/v2.1/window-functions.png' | relative_url }}" alt="Window function diagram" style="border:1px solid #eee;max-width:100%" />

## Caveats

The most important part of working with window functions is understanding what data will be in the frame that the window function will be operating on.

By default, the window frame extends from the first row in the partition to the current row.  If you order the partition (using `OVER (PARTITION BY x ORDER BY y)`) the default frame changes to be the entire partition.  Because of this, you should be aware of the behavior of any aggregate function you use as a window function (or use an explicit `RANGE` clause to constrain the size of the window frame).

In other words, adding an `ORDER BY` clause when you create the window frame (e.g. `PARTITION BY x ORDER by y`) has the following effects:

- It makes the rows inside the window frame ordered (as you expected)
- It changes what rows the function is called on - no longer all of the rows in the window frame, but a subset between the "first" row and the current row (possibly not as you expected)

Yet another way of saying this is that we can run a window function on either:

- All rows in the window frame created by the  `PARTITION BY` clause, e.g., `SELECT F(x) OVER () FROM z`.
- A subset of the rows in the window frame if the frame is created with `SELECT F(x) OVER (PARTITION BY x ORDER BY y) FROM z`.

If you are not seeing results you expect from your window functions, this behavior may explain why.

## Examples

The examples in this section use the "users", "rides", and "vehicles" tables from the 'movr' database used in the [CockroachDB 2.0 demo][demo].  We are planning to open source the movr data set in the 2.1 release timeframe.  When it's out we will update this page with a link to the repo.

### Schema

The tables used in the examples are shown below.

{% include copy-clipboard.html %}
~~~ sql
> SHOW CREATE TABLE users;
~~~

~~~
+-------+-------------------------------------------------------------+
| Table |                         CreateTable                         |
+-------+-------------------------------------------------------------+
| users | CREATE TABLE users (                                        |
|       |     id UUID NOT NULL,                                       |
|       |     city STRING NOT NULL,                                   |
|       |     name STRING NULL,                                       |
|       |     address STRING NULL,                                    |
|       |     credit_card STRING NULL,                                |
|       |     CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),    |
|       |     FAMILY "primary" (id, city, name, address, credit_card) |
|       | )                                                           |
+-------+-------------------------------------------------------------+
~~~

{% include copy-clipboard.html %}
~~~ sql
> SHOW CREATE TABLE rides;
~~~

~~~
+-------+--------------------------------------------------------------------------+
| Table |                               CreateTable                                |
+-------+--------------------------------------------------------------------------+
| rides | CREATE TABLE rides (                                                     |
|       |     id UUID NOT NULL,                                                    |
|       |     city STRING NOT NULL,                                                |
|       |     vehicle_city STRING NULL,                                            |
|       |     rider_id UUID NULL,                                                  |
|       |     vehicle_id UUID NULL,                                                |
|       |     start_address STRING NULL,                                           |
|       |     end_address STRING NULL,                                             |
|       |     start_time TIMESTAMP NULL,                                           |
|       |     end_time TIMESTAMP NULL,                                             |
|       |     revenue FLOAT NULL,                                                  |
|       |     CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),                 |
|       |     CONSTRAINT fk_city_ref_users FOREIGN KEY (city, rider_id) REFERENCES |
|       | users (city, id),                                                        |
|       |     INDEX rides_auto_index_fk_city_ref_users (city ASC, rider_id ASC),   |
|       |     CONSTRAINT fk_vehicle_city_ref_vehicles FOREIGN KEY (vehicle_city,   |
|       | vehicle_id) REFERENCES vehicles (city, id),                              |
|       |     INDEX rides_auto_index_fk_vehicle_city_ref_vehicles (vehicle_city    |
|       | ASC, vehicle_id ASC),                                                    |
|       |     FAMILY "primary" (id, city, vehicle_city, rider_id, vehicle_id,      |
|       | start_address, end_address, start_time, end_time, revenue),              |
|       |     CONSTRAINT check_vehicle_city_city CHECK (vehicle_city = city)       |
|       | )                                                                        |
+-------+--------------------------------------------------------------------------+
~~~

{% include copy-clipboard.html %}
~~~ sql
> SHOW CREATE TABLE vehicles;
~~~

~~~
+----------+------------------------------------------------------------------------------------------------+
|  Table   |                                          CreateTable                                           |
+----------+------------------------------------------------------------------------------------------------+
| vehicles | CREATE TABLE vehicles (                                                                       +|
|          |         id UUID NOT NULL,                                                                     +|
|          |         city STRING NOT NULL,                                                                 +|
|          |         type STRING NULL,                                                                     +|
|          |         owner_id UUID NULL,                                                                   +|
|          |         creation_time TIMESTAMP NULL,                                                         +|
|          |         status STRING NULL,                                                                   +|
|          |         mycol STRING NULL,                                                                    +|
|          |         ext JSON NULL,                                                                        +|
|          |         CONSTRAINT "primary" PRIMARY KEY (city ASC, id ASC),                                  +|
|          |         CONSTRAINT fk_city_ref_users FOREIGN KEY (city, owner_id) REFERENCES users (city, id),+|
|          |         INDEX vehicles_auto_index_fk_city_ref_users (city ASC, owner_id ASC),                 +|
|          |         FAMILY "primary" (id, city, type, owner_id, creation_time, status, mycol, ext)        +|
|          | )                                                                                              |
+----------+------------------------------------------------------------------------------------------------+
(1 row)
~~~

### The most rides

To see which customers have taken the most rides:

{% include copy-clipboard.html %}
~~~ sql
> SELECT * FROM
    (SELECT distinct(name) as "name",
            COUNT(*) OVER (PARTITION BY name) AS "number of rides"
     FROM users JOIN rides ON users.id = rides.rider_id)
  ORDER BY "number of rides" DESC LIMIT 10;
~~~

~~~
+-------------------+-----------------+
|       name        | number of rides |
+-------------------+-----------------+
| Michael Smith     |              53 |
| Michael Williams  |              37 |
| John Smith        |              36 |
| Jennifer Smith    |              32 |
| Michael Brown     |              31 |
| Michael Miller    |              30 |
| Christopher Smith |              29 |
| James Johnson     |              28 |
| Jennifer Johnson  |              27 |
| Amanda Smith      |              26 |
+-------------------+-----------------+
(10 rows)
~~~

### The most revenue

To see which customers have generated the most revenue, run:

{% include copy-clipboard.html %}
~~~ sql
SELECT DISTINCT name,
  SUM(revenue) over (partition BY name) AS "total rider revenue"
  FROM users JOIN rides ON users.id = rides.rider_id
  ORDER BY "total rider revenue" DESC
  LIMIT 10;
~~~

~~~
+------------------+---------------------+
|       name       | total rider revenue |
+------------------+---------------------+
| Michael Jones    |  465.25328956751196 |
| James Jones      |   350.0380740792208 |
| Michael Thompson |  329.07722514046185 |
| Steven Lane      |  308.08198141368615 |
| Jennifer Davis   |  297.05709764285797 |
| John Hernandez   |  286.40393951577124 |
| David Smith      |  282.10831776351614 |
| Vanessa Brown    |  281.73030695407414 |
| James Baker      |  280.59061211182495 |
| Robert Hernandez |  264.51810028779965 |
+------------------+---------------------+
(10 rows)
~~~

### Add row numbers to query output

To add row numbers to the output, kick the previous query down into a subquery and run the `row_number()` window function.

{% include copy-clipboard.html %}
~~~ sql
SELECT *, ROW_NUMBER() OVER () FROM (SELECT DISTINCT name,
  SUM(revenue) over (partition BY name) AS "total rider revenue"
  FROM users JOIN rides ON users.id = rides.rider_id
  ORDER BY "total rider revenue" DESC
  LIMIT 10);
~~~

~~~
+------------------+---------------------+------------+
|       name       | total rider revenue | row_number |
+------------------+---------------------+------------+
| Michael Smith    |             2251.04 |          1 |
| Jennifer Smith   |             2114.55 |          2 |
| Michael Williams |             2011.85 |          3 |
| John Smith       |             1826.43 |          4 |
| Robert Johnson   |             1652.99 |          5 |
| Michael Miller   |             1619.25 |          6 |
| Robert Smith     |             1534.11 |          7 |
| Jennifer Johnson |             1506.50 |          8 |
| Michael Brown    |             1478.90 |          9 |
| Michael Johnson  |             1405.68 |         10 |
+------------------+---------------------+------------+
(10 rows)
~~~

### The most revenue AND the most rides

To see which customers have generated the most revenue while also taking the most rides, do:

{% include copy-clipboard.html %}
~~~ sql
SELECT * FROM (
  SELECT DISTINCT name,
    COUNT(*)     OVER w AS "number of rides",
    (SUM(revenue) OVER w)::DECIMAL(100,2) AS "total rider revenue"
    FROM users JOIN rides ON users.ID = rides.rider_id
    WINDOW w AS (PARTITION BY name)
  )
     ORDER BY "number of rides" DESC,
           "total rider revenue" DESC
  LIMIT 10;
~~~

~~~
+-------------------+-----------------+---------------------+
|       name        | number of rides | total rider revenue |
+-------------------+-----------------+---------------------+
| Michael Smith     |              53 |             2251.04 |
| Michael Williams  |              37 |             2011.85 |
| John Smith        |              36 |             1826.43 |
| Jennifer Smith    |              32 |             2114.55 |
| Michael Brown     |              31 |             1478.90 |
| Michael Miller    |              30 |             1619.25 |
| Christopher Smith |              29 |             1380.18 |
| James Johnson     |              28 |             1378.78 |
| Jennifer Johnson  |              27 |             1506.50 |
| Robert Johnson    |              26 |             1652.99 |
+-------------------+-----------------+---------------------+
(10 rows)
~~~

### Highest average revenue per ride

To see which customers have the highest average revenue per ride, run:

{% include copy-clipboard.html %}
~~~ sql
SELECT name,
  COUNT(*)     OVER w AS "number of rides",
  AVG(revenue) OVER w AS "average revenue per ride"
  FROM users JOIN rides ON users.ID = rides.rider_id
  WINDOW w AS (PARTITION BY name)
  ORDER BY "average revenue per ride" DESC, "number of rides" ASC
  LIMIT 10;
~~~

~~~
+-------------------+-----------------+--------------------------+
|       name        | number of rides | average revenue per ride |
+-------------------+-----------------+--------------------------+
| Ann Johnson       |               1 |        99.99940404943563 |
| Zachary Terry     |               1 |        99.99713547304452 |
| Michelle Johnson  |               1 |        99.99284158049196 |
| Walter Blake      |               1 |        99.98980862800644 |
| Robert Carr       |               1 |         99.9733715337187 |
| Jeffery Walker    |               1 |        99.95812364841187 |
| Kristin Smith     |               1 |         99.9472029441925 |
| Stephanie Sharp   |               1 |        99.94129781533725 |
| Reginald Schwartz |               1 |        99.92882925427865 |
| Lisa Ross         |               1 |        99.92666994099285 |
+-------------------+-----------------+--------------------------+
(10 rows)
~~~

### Highest average revenue per ride, given more than one ride

To see which customers have the highest average revenue per ride, given that they have taken at least 3 rides, run:

{% include copy-clipboard.html %}
~~~ sql
SELECT * FROM (
  SELECT DISTINCT name,
    COUNT(*)     OVER w AS "number of rides",
    AVG(revenue) OVER w AS "average revenue per ride"
    FROM users JOIN rides ON users.ID = rides.rider_id
    WINDOW w AS (PARTITION BY name)
  )
  WHERE "number of rides" >= 3
  ORDER BY "average revenue per ride" DESC
  LIMIT 10;
~~~

~~~
+---------------------+-----------------+--------------------------+
|        name         | number of rides | average revenue per ride |
+---------------------+-----------------+--------------------------+
| Jonathan Richardson |               3 |    98.076666666666666667 |
| Luis Haas           |               3 |                    96.64 |
| Jay Singleton       |               3 |                    96.19 |
| Kyle Mccall         |               3 |    95.576666666666666667 |
| Christopher Escobar |               3 |    95.276666666666666667 |
| Madison Lester      |               3 |    95.046666666666666667 |
| Heather Rose        |               3 |    94.823333333333333333 |
| Angela Dawson       |               4 |                   94.705 |
| Stephanie Mora      |               3 |    94.426666666666666667 |
| Trevor Garcia       |               3 |    94.363333333333333333 |
+---------------------+-----------------+--------------------------+
(10 rows)
~~~

### Total number of riders, and total revenue

To find out the total number of riders and total revenue generated thus far by the app, do:

{% include copy-clipboard.html %}
~~~ sql
SELECT
  COUNT("name") AS "total # of riders",
  SUM("total rider revenue") AS "total revenue" FROM (
    SELECT name,
           SUM(revenue) over (partition BY name) AS "total rider revenue"
      FROM users JOIN rides ON users.id = rides.rider_id
      ORDER BY "total rider revenue" DESC
      LIMIT (SELECT count(distinct(rider_id)) FROM rides)
);
~~~

~~~
+-------------------+---------------+
| total # of riders | total revenue |
+-------------------+---------------+
|             63117 |   15772911.41 |
+-------------------+---------------+
(1 row)
~~~

### How many of each vehicle type

{% include copy-clipboard.html %}
~~~ sql
SELECT DISTINCT type, COUNT(*) OVER (PARTITION BY TYPE) AS cnt FROM vehicles ORDER BY cnt DESC;
~~~

~~~
+------------+-------+
|    type    |  cnt  |
+------------+-------+
| bike       | 33377 |
| scooter    | 33315 |
| skateboard | 33307 |
+------------+-------+
(3 rows)
~~~

### Revenue per city

{% include copy-clipboard.html %}
~~~ sql
SELECT DISTINCT(city), SUM(revenue) OVER (PARTITION BY city) AS city_revenue FROM rides ORDER BY city_revenue DESC;
~~~
 
~~~
+---------------+--------------+
|    (city)     | city_revenue |
+---------------+--------------+
| paris         |    567144.48 |
| washington dc |    567011.74 |
| amsterdam     |    564211.74 |
| new york      |    561420.67 |
| rome          |    560464.52 |
| boston        |    559465.75 |
| san francisco |    558807.13 |
| los angeles   |    558805.45 |
| seattle       |    555452.08 |
+---------------+--------------+
(9 rows)
~~~

## See Also

- [Simple `SELECT` clause][simple-select]
- [Selection Queries][selection-query]
- [Aggregate functions][agg]
- [CockroachDB 2.0 Demo][demo]

<!-- References -->

[agg]: functions-and-operators.html#anyelement-functions
[demo]: https://www.youtube.com/watch?v=v2QK5VgLx6E
[simple-select]: select-clause.html
[selection-query]: selection-queries.html
