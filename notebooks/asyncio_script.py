import asyncio

async def my_func1():
    print("Hello, World!")

async def my_func2():
    print("second function")

async def main():
    print("Starting main function")
    await my_func1()
    await my_func2() 

asyncio.run(main())