# [driverless-fp-collector]((https://kaliiiiiiiiii.github.io/driverless-fp-collector/))

**checkout the [demo](https://kaliiiiiiiiii.github.io/driverless-fp-collector/)**

* fetch fingerprint for [`selenium-driverless`](https://github.com/kaliiiiiiiiii/Selenium-Driverless) (applying fingerprints not yet implemented)

### Usage
place the script at [src/fingerprint.js](src/fingerprint.js) on your WebPage
```js
async function collect_fingerprint(click_elem=document.documentElement,check_bot=true, get_gl=true, check_worker=true){...}
```
- `click_elem:HTMLElement=document.documentElement` element to expect click on
- `check_bot=true` requires touch or click events
- `get_gl=true` will unavoidably show warnings in the console [stack-overflow](https://stackoverflow.com/questions/39515468/how-do-i-disable-webgl-error-mesasges-warnings-in-the-console)
- `check_worker=true` requires "blob:" urls to be allowed (`"Content-Security-Policy: worker-src 'self' blob:"` header might work)

```js
// example script
async function handler(){
        data = collect_fingerprint(document.documentElement,true, true, true);
        data = await data
        console.log(data);
        
        return JSON.stringify(data)
        // or send back to your server//backend//DataBase
    }
res = handler()
res.catch((e) => {console.error(e))
```

You can find a example output at [sample_output.json](sample_output.json)
## Help

Please feel free to open an issue or fork! \
Note: **please check the todo's below at first!**

## Todo's
<details>
<summary>Click to expand</summary>

- no TODO's yet
</details>

## Authors

Copyright and Author: \
[Aurin Aegerter](mailto:aurinliun@gmx.ch) (aka **Steve**)

## License
see [LICENSE.md](LICENSE.md)

#### Third pary
for files in [/docs](/docs) and [demo](https://kaliiiiiiiiii.github.io/driverless-fp-collector/) as well: [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer) and [jquery](https://github.com/jquery/jquery), which each have their own licence
## Disclaimer

I am not responsible what you use the code for!!! Also no warranty!

## Acknowledgments

Inspiration, code snippets, etc.
* [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer)
