'''
How to call async python function ??

Calling async function works different than calling not async function !!!

'''

# In normal Python:
def add():
    return 5

x = add() # add() executes immediately.




# But in async Python:
async def add():
    return 5

x = add() # add() does NOT run.
          # It only creates a coroutine object — basically a paused task.
          # really means: Create a plan for running add later. Not exactly run add() now"

'''
Learning:
1. async functions needs event loops to schedule and run it.


The Event Loop is the Real Boss
This is the MOST important async concept.

The event loop:

    schedules tasks
    pauses tasks
    resumes tasks
    switches between tasks
    handles waiting operations

'''

# Your code: creates a coroutine object. To actually RUN it, Python needs an event 
# loop.
async def add():
    return 5

x = add()



# Simplest Way
import asyncio
async def add():
    return 5

x = asyncio.run(add())
print(x)


'''
What asyncio.run() does internally. It basically:

    Creates event loop
    Runs coroutine
    Waits for completion
    Closes loop

So this:
asyncio.run(add())

means:
"Hey Python, create an event loop and execute this coroutine."

'''
#############################################
#################
############################################

'''
If async def            -> Creates pause-able function.
   asyncio.run()        -> Starts event loop and executes async function.

Then,
    await               -> Pause here while waiting for something slow.

Lets learn await....
'''

import asyncio

async def add():
    print("Start")
    await asyncio.sleep(2) # "Pause here for 2 seconds, but don't block entire program.", it allows event loop to do other work meanwhile.
                           # Why not use time.sleep(2)? It blocks everything.
    print("Done")
    return 5
x = asyncio.run(add())
print(x)


'''
MOST IMPORTANT UNDERSTANDING

await only works INSIDE async functions.
Why?
Because only async functions know how to pause/resume.
Normal functions cannot pause halfway.
'''

## Note: We will use main () now
import asyncio

async def add():
    return 5

async def main():
    x = await add()
    print(x)

asyncio.run(main())

####    Inside an async function, if you call another async function and want its result/execution, 
#       you usually use await.

'''
Things left to master:

await
asyncio.create_task()
concurrent execution
asyncio.gather()
task lifecycle
cancellation
asyncio.wait_for()
timeout handling
async context managers (async with)
async iterators (async for)



blocking vs non-blocking
ThreadPoolExecutor : run_in_executor
async HTTP : aiohttp, httpx.AsyncClient
threads vs async vs multiprocessing
GIL
async queues
streaming
distributed systems concepts


Event Loop Internals
scheduling
cooperative multitasking
ready queue
selectors/epoll
Futures vs Tasks vs Coroutines


Backpressure
streaming systems
websockets
Kafka
AI token streaming


Concurrency vs Parallelism
GIL (Global Interpreter Lock)
Threads vs Async vs Multiprocessing

'''
