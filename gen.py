# https://github.com/kaliiiiiiiiii/driverless-fp-collector

from selenium_driverless import webdriver
from selenium_driverless.types.by import By
import os
import asyncio
import json


async def get_fp(driver, script):
    await driver.get(os.getcwd() + "/docs/index.html")
    await asyncio.sleep(1)
    res = asyncio.create_task(driver.execute_async_script(script, timeout=120))
    elem = await driver.find_element(By.ID, "get-fp")
    await asyncio.sleep(0.5)
    await elem.click(move_to=False)
    await asyncio.sleep(0.5)
    await elem.click(move_to=False)
    res = await res
    res = json.loads(res)
    return res


async def get_fp_native(script):
    async with webdriver.Chrome(debug=False) as driver:
        res = await get_fp(driver, script)
        return res


async def get_fp_headless(script):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    async with webdriver.Chrome(debug=False, options=options) as headles_driver:
        res = await get_fp(headles_driver, script)
        return res


async def main():
    os.system("npm run build")
    script = """
    // execute
    async function handler(){
        var elem = document.documentElement;
        function callback(e){
            window.fp_click_callback(e)
            elem.removeEventListener("mousedown", this);
            elem.removeEventListener("touchstart", this);
        }
        var data = getFingerprint(document.querySelector("#get-fp"), true, true);
        elem.addEventListener("mousedown", callback);
        elem.addEventListener("touchstart", callback);
        data = await data
        console.log(data);
        return JSON.stringify(data)
        debugger
    }
    res = handler()
    res.catch((e) => {throw e})
    res.then(arguments[arguments.length-1])
    """

    fp_native, fp_headless = await asyncio.gather(
        get_fp_native(script), get_fp_headless(script)
    )
    with open(os.getcwd() + "/sample_output.json", "w+", encoding="utf-8") as f:
        f.write(json.dumps(fp_native, indent=4))
    with open(
        os.getcwd() + "/sample_output_headless.json", "w+", encoding="utf-8"
    ) as f:
        f.write(json.dumps(fp_headless, indent=4))


asyncio.run(main())
