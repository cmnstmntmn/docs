import argparse
import psycopg2
import time

parser = argparse.ArgumentParser(
    description="test performance of statements against movr database")
parser.add_argument("--host", required=True,
    help="ip address of one of the CockroachDB nodes")
parser.add_argument("--statement", required=True,
    help="statement to execute")
parser.add_argument("--repeat",
    help="number of times to repeat the statement", default = 20)
parser.add_argument("--cumulative",
    help="print cumulative time for all executed statements", action="store_true")
args = parser.parse_args()

conn = psycopg2.connect(database='movr', user='root', host=args.host, port=26257)
conn.set_session(autocommit=True)
cur = conn.cursor()

times = list()
count = 0
for n in range(int(args.repeat)):
    start = time.time()
    statement = args.statement
    cur.execute(statement)
    if count < 1:
        try:
            rows = cur.fetchall()
            for row in rows:
                print("")
                print("Result:", [str(cell) for cell in row])
        except Exception as e:
            # print(e)
            pass
    end = time.time()
    times.append(end - start)
    count += 1

cur.close()
conn.close()

print("")
print("Times:", times)
print("")
print("Average time:", float(sum(times))/len(times))
print("")
if args.cumulative:
    print("Cumulative time:", sum(times))
    print("")




# MULTIPROCESSING
#
# import argparse
# import multiprocessing
# import psycopg2
# import time
#
# parser = argparse.ArgumentParser(
#     description = "test performance of queries against movr database")
# parser.add_argument("--host", required=True,
#     help="ip address of one of the CockroachDB nodes")
# parser.add_argument("--query", required=True,
#     help="statement to execute alone or in a batch")
# parser.add_argument("--count",
#     help="number of times to execute the statement or batch", default = 20)
# parser.add_argument("--batch",
#     help="number of statements to send as a batch", default = 1)
# parser.add_argument("--concurrency",
#     help="number of concurrent connections", default = 1)
# args = parser.parse_args()
#
# times = list()
# def db_connection():
#     conn = psycopg2.connect(database='movr', user='root', host=args.host, port=26257)
#     conn.set_session(autocommit=True)
#     cur = conn.cursor()
#
#     for n in range(int(args.count)):
#         start = time.time()
#         if int(args.batch) > 1:
#             values = args.query[args.query.find("("):args.query.rfind(")")+1] + ","
#             query = args.query[:-1] + "," + (values * int(args.batch))
#             cur.execute(query[:-1])
#         else:
#             query = args.query
#             cur.execute(query)
#         try:
#             rows = cur.fetchall()
#             for row in rows:
#                 print([str(cell) for cell in row])
#         except Exception as e:
#             print(e)
#             pass
#         end = time.time()
#         times.append(end - start)
#
#     cur.close()
#     conn.close()
#     return
#
# if __name__ == '__main__':
#     jobs = []
#     for i in range(int(args.concurrency)):
#         p = multiprocessing.Process(target=db_connection)
#         jobs.append(p)
#         p.start()
#
#     for p in jobs:
#         p.join()
#
#     # print("Query:", query)
#     # print("")
#     # print("Times:", times)
#     # print("")
#     print("Cumulative time:", sum(times))
#     print("")
#     print("Average:", float(sum(times))/len(times))
#     print("")
#     print("Threads:", threads)

# MULTITHREADING
#
# import argparse
# import psycopg2
# import time
# import threading
#
# parser = argparse.ArgumentParser(
#     description = "test performance of queries against movr database")
# parser.add_argument("--host", required=True,
#     help="ip address of one of the CockroachDB nodes")
# parser.add_argument("--query", required=True,
#     help="statement to execute alone or in a batch")
# parser.add_argument("--count",
#     help="number of times to execute the statement or batch", default = 20)
# parser.add_argument("--batch",
#     help="number of statements to send as a batch", default = 1)
# parser.add_argument("--concurrency",
#     help="number of concurrent connections", default = 1)
# args = parser.parse_args()
#
# def db_connection():
#     conn = psycopg2.connect(database='movr', user='root', host=args.host, port=26257)
#     conn.set_session(autocommit=True)
#     cur = conn.cursor()
#
#     for n in range(int(args.count)):
#         start = time.time()
#         if int(args.batch) > 1:
#             values = args.query[args.query.find("("):args.query.rfind(")")+1] + ","
#             query = args.query[:-1] + "," + (values * int(args.batch))
#             cur.execute(query[:-1])
#         else:
#             query = args.query
#             cur.execute(query)
#         try:
#             rows = cur.fetchall()
#             for row in rows:
#                 print([str(cell) for cell in row])
#         except Exception as e:
#             print(e)
#             pass
#         end = time.time()
#         times.append(end - start)
#
#     cur.close()
#     conn.close()
#
# times = list()
# threads = list()
# for n in range(int(args.concurrency)):
#     t = threading.Thread(target=db_connection)
#     threads.append(t)
#     t.start()
#
# for t in threads:
#     t.join()
#
# print("Query:", query)
# print("")
# print("Times:", times)
# print("")
# print("Cumulative time:", sum(times))
# print("")
# print("Average:", float(sum(times))/len(times))
# print("")
# print("Threads:", threads)
