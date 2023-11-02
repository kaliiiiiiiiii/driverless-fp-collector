# FP-Collector

Simple script for collecting some unique information from browsers

**checkout the [demo](https://github.com/kaliiiiiiiiii/Selenium-Driverless)**

-   fetch fingerprint for [`selenium-driverless`](https://github.com/kaliiiiiiiiii/Selenium-Driverless) (applying fingerprints not yet implemented)

### Feel free to contribute!

See dev-branch for the latest features.

### Usage

You can embed the script into your website using a free CDN.

```html
<script type="text/javascript" src="://unpkg.com/fp-collector"><script>
```

```js
const fp = await getFingerprint(
    (click_elem = document.querySelector("button")),
    (check_bot = true),
    (get_gl = true),
    (check_worker = true),
);
```

-   `click_elem:HTMLElement=document.documentElement` element to expect click on
-   `check_bot=true` requires touch or click events
-   `get_gl=true` will unavoidably show warnings in the console [stack-overflow](https://stackoverflow.com/questions/39515468/how-do-i-disable-webgl-error-mesasges-warnings-in-the-console)
-   `check_worker=true` requires `blob:` urls to be allowed (`"Content-Security-Policy: worker-src 'self' blob:"` header might work)

```js
// example script
async function handler() {
    const data = await getFingerprint(document.querySelector("button"), true, true, false);
    return JSON.stringify(data);
}
```

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

for files in [/docs](/docs) and [demo](https://kaliiiiiiiiii.github.io/driverless-fp-collector/) as well: [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer) and [jquery](https://github.com/jquery/jquery), which each have their own licence

## Disclaimer

I am not responsible what you use the code for!!! Also no warranty!

## Acknowledgments

Inspiration, code snippets, etc.

-   [jquery.json-viewer](https://github.com/abodelot/jquery.json-viewer)
-   [jquery](https://github.com/jquery/jquery)
-   [creep-js](https://github.com/abrahamjuliot/creepjs)
