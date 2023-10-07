# https://github.com/kaliiiiiiiiii/driverless-fp-collector

from selenium_driverless import webdriver
import os
import asyncio
import json


async def main():
    with open(os.getcwd() + "/src/fingerprint.js", "r", encoding="utf-8") as f:
        fingerprint_js = f.read()

    script = fingerprint_js + """
    // execute
    async function handler(){
        data = collect_fingerprint(document.documentElement,true, true, true);
        document.documentElement.click()
        data = await data
        console.log(data);
        return JSON.stringify(data)
    }
    res = handler()
    res.catch((e) => {throw e})
    res.then(arguments[arguments.length-1])
    """

    async with webdriver.Chrome(debug=True) as driver:
        await driver.get("https://wikipedia.org")
        await asyncio.sleep(1)
        res = asyncio.create_task(driver.execute_async_script(script, timeout=60))
        await asyncio.sleep(1)
        await driver.execute_script("document.documentElement.click()")
        res = await res
        res = json.loads(res)
        with open("sample_output.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(res, indent=4))


asyncio.run(main())
