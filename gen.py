# https://github.com/kaliiiiiiiiii/driverless-fp-collector

from selenium_driverless import webdriver
from selenium_driverless.types.by import By
import os
import asyncio
import json


async def get_fp(driver, script):
    await driver.get(os.getcwd() + "/docs/index.html")
    await asyncio.sleep(1)
    res = asyncio.create_task(driver.execute_async_script(script, timeout=60))
    await asyncio.sleep(1)
    elem = await driver.find_element(By.ID, "get-fp")
    await elem.click(move_to=False)
    res = await res
    res = json.loads(res)
    return res


async def get_fp_native(script):
    async with webdriver.Chrome(debug=True) as driver:
        res = await get_fp(driver, script)
        return res


async def get_fp_headless(script):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    async with webdriver.Chrome(debug=True, options=options) as headles_driver:
        res = await get_fp(headles_driver, script)
        return res


async def main():
    with open(os.getcwd() + "/src/fingerprint.js", "r", encoding="utf-8") as f:
        fingerprint_js = f.read()

    script = fingerprint_js + """
    // execute
    async function handler(){
        data = collect_fingerprint(document.querySelector("#get-fp"),true, true, true);
        document.documentElement.click()
        data = await data
        console.log(data);
        return JSON.stringify(data)
    }
    res = handler()
    res.catch((e) => {throw e})
    res.then(arguments[arguments.length-1])
    """

    fp_native, fp_headless = await asyncio.gather(
        get_fp_native(script),
        get_fp_headless(script)
    )
    with open(os.getcwd() + "/sample_output.json", "w+", encoding="utf-8") as f:
        f.write(json.dumps(fp_native, indent=4))
    with open(os.getcwd() + "/sample_output_headless.json", "w+", encoding="utf-8") as f:
        f.write(json.dumps(fp_headless, indent=4))


asyncio.run(main())
