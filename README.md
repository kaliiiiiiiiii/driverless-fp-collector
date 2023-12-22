# FP-Collector

Simple script for collecting some unique information from browsers

**checkout the [demo](https://fp.totallysafe.ch/)**

-   fetch fingerprint for [`selenium-driverless`](https://github.com/kaliiiiiiiiii/Selenium-Driverless) (applying fingerprints not yet implemented)

### Feel free to contribute!

See dev-branch for the latest features.

### Usage

You can embed the script into your website using a free CDN.

```html
<script type="text/javascript" src="://unpkg.com/fp-collector"><script>
```

```js
var elem = document.documentElement;
function callback(e){
    window.fp_click_callback(e)
    elem.removeEventListener("mousedown", this);
    elem.removeEventListener("touchstart", this);
    elem.removeEventListener("touchmove", this);
    elem.removeEventListener("mousemove", this);
}
var data = getFingerprint(true, false);
elem.addEventListener("mousedown", callback);
elem.addEventListener("touchstart", callback);
elem.addEventListener("touchmove", callback);
elem.addEventListener("mousemove", callback);
data = await data
// globalThis.on_fp_result
// send_back(JSON.stringify(data)
```
```javascript
async function getFingerprint(get_gl=true, check_worker=true){...}
```
-   `get_gl=true` will unavoidably show warnings in the console [stack-overflow](https://stackoverflow.com/questions/39515468/how-do-i-disable-webgl-error-mesasges-warnings-in-the-console)
-   `check_worker=true` requires `blob:` urls to be allowed (`"Content-Security-Policy: worker-src 'self' blob:"` header might work)

You can find some example output at [sample_output.json](sample_output.json)

## Help

Please feel free to open an issue or fork! \
Note: **please check the todo's below at first!**

## Todo's

<details>
<summary>Click to expand</summary>

-   no TODO's yet
</details>

## Authors

Copyright and Author: \
[Aurin Aegerter](mailto:aurinliun@gmx.ch) (aka **Steve**)

Cleanups, NPM:
[Peet](https://peet.ws)

## License

fp-collector is licensed under the MIT license!
See [LICENSE.md](LICENSE.md)

#### Third pary

for the [demo](https://fp.totallysafe.ch/) as well: [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer) and [jquery](https://github.com/jquery/jquery), which each have their own licence

## Disclaimer

I am not responsible what you use the code for!!! Also no warranty!

## Acknowledgments

Inspiration, code snippets, etc.

-   [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer)
-   [jquery](https://github.com/jquery/jquery)
-   [creep-js](https://github.com/abrahamjuliot/creepjs)
