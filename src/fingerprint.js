// https://github.com/kaliiiiiiiiii/driverless-fp-collector

/*
MIT License

Copyright (c) 2023 Aurin Aegerter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

const { fonts, permissions, audioTypes, videoTypes } = require("./constants");

// main function
async function getFingerprint(
    click_elem = document.documentElement,
    get_gl = true,
    check_worker = true,
) {
    // utils
    function j(obj, max_depth = 2) {
        // to json
        if (max_depth === 0) {
            return undefined;
        }
        if (
            obj &&
            obj.constructor &&
            typeof obj.constructor.length == "number" &&
            obj.constructor.name.includes("Array")
        ) {
            var res = [];
            Object.values(obj).forEach((value) => {
                if (typeof value === "object") {
                    value = j(value, max_depth - 1);
                }
                var _type = typeof value;
                if (!["function"].includes(_type)) {
                    res.push(value);
                }
            });
            return res;
        } else if (obj) {
            var res = {};
            get_obj_keys(obj).forEach((key) => {
                var value = obj[key];
                if (typeof value === "object") {
                    value = j(value, max_depth - 1);
                }
                var _type = typeof value;
                if (obj !== undefined && !["function"].includes(_type)) {
                    res[key] = value;
                }
            });
            return res;
        }
    }

    function get_worker_response(fn) {
        try {
            const URL = window.URL || window.webkitURL;
            var fn = "self.onmessage=async function(e){postMessage(await (" + fn.toString() + ")())}";
            var blob;
            try {
                blob = new Blob([fn], { type: "application/javascript" });
            } catch (e) {
                // Backwards-compatibility
                window.BlobBuilder = window.BlobBuilder || window.WebKitBlobBuilder || window.MozBlobBuilder;
                blob = new BlobBuilder();
                blob.append(response);
                blob = blob.getBlob();
            }
            var url = URL.createObjectURL(blob);
            var worker = new Worker(url);
            var _promise = new Promise((resolve, reject) => {
                worker.onmessage = (m) => {
                    worker.terminate();
                    resolve(m.data);
                };
            });
            worker.postMessage("call");
            return _promise;
        } catch (e) {
            return new Promise((resolve, reject) => {
                reject(e);
            });
        }
    }

    async function get_permission_state(permission) {
        try {
            var result = await navigator.permissions.query({ name: permission });
            return result.state;
        } catch (e) {}
    }

    function get_obj_keys(obj) {
        var res = new Set(Object.getOwnPropertyNames(obj));
        for (var prop in obj) {
            res.add(prop);
        }
        return [...res];
    }

    function get_speech() {
        return new Promise(function (resolve, reject) {
            var speech = speechSynthesis.getVoices();
            if (speech.length === 0) {
                setTimeout(() => {
                    resolve([]);
                }, 2000); // in case voices are actually 0 and already have been loaded
                speechSynthesis.addEventListener("voiceschanged", () => {
                    resolve(speechSynthesis.getVoices());
                });
            } else {
                resolve(speech);
            }
        });
    }

    function checkAudioType(_type) {
        const audio = document.createElement("audio");
        return audio.canPlayType(_type);
    }

    // functions
    function get_audio_types() {
        var res = {};
        audioTypes.forEach((t) => {
            res[t] = checkAudioType(t);
        });
        return res;
    }
    async function listFonts() {
        await document.fonts.ready;

        const fontAvailable = new Set();

        for (const font of fonts.values()) {
            if (document.fonts.check(`12px "${font}"`)) fontAvailable.add(font);
        }
        return [...fontAvailable.values()];
    }

    async function get_permissions() {
        var res = {};
        permissions.forEach(async function (permission) {
            res[permission] = await get_permission_state(permission);
        });
        return res;
    }

    function get_stack() {
        var sizeA = 0;
        var sizeB = 0;
        var counter = 0;
        try {
            var fn_1 = function () {
                counter += 1;
                fn_1();
            };
            fn_1();
        } catch (_a) {
            sizeA = counter;
            try {
                counter = 0;
                var fn_2 = function () {
                    var local = 1;
                    counter += local;
                    fn_2();
                };
                fn_2();
            } catch (_b) {
                sizeB = counter;
            }
        }
        var bytes = (sizeB * 8) / (sizeA - sizeB);
        return [sizeA, sizeB, bytes];
    }

    function getTimingResolution() {
        var runs = 5000;
        var valA = 1;
        var valB = 1;
        var res;
        for (var i = 0; i < runs; i++) {
            var a = performance.now();
            var b = performance.now();
            if (a < b) {
                res = b - a;
                if (res > valA && res < valB) {
                    valB = res;
                } else if (res < valA) {
                    valB = valA;
                    valA = res;
                }
            }
        }
        return valA;
    }

    async function ensure_no_bot(check_worker, click_promise) {
        e = await globalThis.fp_click_promise
        globalThis.fp_click_promise = new Promise((resolve, reject)=>{globalThis.fp_click_callback = resolve})
        var is_touch = false;
        if (e.type == "touchstart") {
            is_touch = true;
            e = e.touches[0] || e.changedTouches[0];
        }
        var is_bot = e.pageY == e.screenY && e.pageX == e.screenX;
        if (is_bot && 1 >= outerHeight - innerHeight) {
            // fullscreen
            is_bot = false;
        }
        if (is_bot && is_touch && navigator.userAgentData.mobile) {
            is_bot = "maybe"; // mobile touch can have e.pageY == e.screenY && e.pageX == e.screenX
        }
        if (is_touch == false && navigator.userAgentData.mobile === true) {
            is_bot = "maybe"; // mouse on mobile is suspicious
        }
        if (e.isTrusted === false) {
            is_bot = true;
        }
        if (check_worker) {
            worker_ua = await get_worker_response(function(){return navigator.userAgent});
            if (worker_ua !== navigator.userAgent) {
                is_bot = true;
            }
        };
        return is_bot
    }

    function get_gl_infos(gl) {
        if (gl) {
            const get = gl.getParameter.bind(gl);
            const ext = gl.getExtension("WEBGL_debug_renderer_info");
            const parameters = {};

            for (const parameter in gl) {
                var param = gl[parameter];
                if (!isNaN(parseInt(param))) {
                    var _res = get(param);
                    if (_res !== null) {
                        parameters[parameter] = [_res, param];
                    }
                }
            }

            if (ext) {
                parameters["UNMASKED_VENDOR_WEBGL"] = [get(ext.UNMASKED_VENDOR_WEBGL), ext.UNMASKED_VENDOR_WEBGL];
                parameters["UNMASKED_RENDERER_WEBGL"] = [get(ext.UNMASKED_RENDERER_WEBGL), ext.UNMASKED_RENDERER_WEBGL];
            }

            return parameters;
        }
    }

    async function get_voices() {
        if (window.speechSynthesis && speechSynthesis.addEventListener) {
            var res = [];
            var voices = await get_speech();
            voices.forEach((value) => {
                res.push(j(value));
            });
            return res;
        }
    }

    async function get_keyboard() {
        if (navigator.keyboard) {
            var res = {};
            const layout = await navigator.keyboard.getLayoutMap();
            layout.forEach((key, value) => {
                res[key] = value;
            });
            return res;
        }
    }
    function audio_context() {
        const audioCtx = new AudioContext();
        return j(audioCtx, 4);
    }

    function get_video() {
        var video = document.createElement("video");
        if (video.canPlayType) {
            var res = {};
            videoTypes.forEach((v) => {
                res[v] = video.canPlayType(v);
            });
            return res;
        }
    }

    async function get_webrtc_infos() {
        var res = {
            video: j(RTCRtpReceiver.getCapabilities("video"), 3),
            audio: j(RTCRtpReceiver.getCapabilities("audio"), 3),
        };
        return res;
    }
    async function get_webgpu_infos() {
        if (navigator.gpu) {
            const adapter = await navigator.gpu.requestAdapter();
            var info = {};
            if (adapter) {
                info = await adapter.requestAdapterInfo();
            }
            var res = { ...j(adapter), ...j(info) };
            return res;
        }
    }

    async function get_media_devices() {
        if (navigator.mediaDevices) {
            var res = await navigator.mediaDevices.enumerateDevices();
            return j(res);
        }
    }

    if (window.chrome) {
        const iframe = document.createElement("iframe");
        iframe.src = "about:blank";
        iframe.height = "0";
        iframe.width = "0";
        var promise = new Promise((resolve) => {
            iframe.addEventListener("load", () => {
                resolve();
            });
        });
        document.body.appendChild(iframe);
        await promise;

        const data = {
            // navigator
            "appCodeName": navigator.appCodeName,
            "appName": navigator.appName,
            "appVersion": navigator.appVersion,
            "cookieEnabled": navigator.cookieEnabled,
            "deviceMemory": navigator.deviceMemory,
            "doNotTrack": navigator.doNotTrack,
            "hardwareConcurrency": navigator.hardwareConcurrency,
            "language": navigator.language,
            "languages": navigator.languages,
            "maxTouchPoints": navigator.maxTouchPoints,
            "pdfViewerEnabled": navigator.pdfViewerEnabled,
            "platform": navigator.platform,
            "product": navigator.product,
            "productSub": navigator.productSub,
            "userAgent": navigator.userAgent,
            "vendor": navigator.vendor,
            "vendorSub": navigator.vendorSub,
            "webdiver": navigator.webdriver,
            "devicePixelRatio": window.devicePixelRatio,
            "innerWidth": window.innerWidth,
            "innerHeight": window.innerHeight,
            "outerWidth": window.outerHeight,
            "outerHeight": window.outerHeight,
            // jsonified
            "screen": j(screen),
            "connection": j(navigator.connection),
            "plugins": j(navigator.plugins, 3),
            "userActivation": j(navigator.userActivation),
            "chrome.app": chrome.app ? j(chrome.app) : undefined,
            // processed
            "wow64": navigator.userAgent.indexOf("WOW64") > -1,
            "HighEntropyValues": j(
                await navigator.userAgentData.getHighEntropyValues([
                    "architecture",
                    "model",
                    "platformVersion",
                    "bitness",
                    "uaFullVersion",
                    "fullVersionList",
                ]),
                3,
            ),
            "darkmode": window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches,
            "availabeFonts": await listFonts(),
            "stack_native": get_stack(),
            "timing_native": getTimingResolution(),
            "permissions": await get_permissions(),
            "navigator": get_obj_keys(navigator),
            "window": get_obj_keys(iframe.contentWindow),
            "document": get_obj_keys(iframe.contentWindow.document),
            "documentElement": get_obj_keys(iframe.contentWindow.document.documentElement),
            "speechSynthesis": await get_voices(),
            "css": j(iframe.contentWindow.getComputedStyle(iframe.contentWindow.document.documentElement, "")),
            "keyboard": await get_keyboard(),
            "audioTypes": get_audio_types(),
            "videoTypes": get_video(),
            "audioContext": audio_context(),
            "webrtc": await get_webrtc_infos(),
            "webgpu": await get_webgpu_infos(),
            "mediaDevices": await get_media_devices(),
            "is_bot": undefined,
            "status": "pass",
        };
        document.body.removeChild(iframe);
        if (check_worker) {
            data["stack_worker"] = await get_worker_response(get_stack);
            data["timing_worker"] = await get_worker_response(getTimingResolution);
        }
        data["is_bot"] = await ensure_no_bot(check_worker, click_elem);
        if (get_gl) {
            const gl = document.createElement("canvas").getContext("webgl");
            const gl2 = document.createElement("canvas").getContext("webgl2");
            const gl_experimental = document.createElement("canvas").getContext("experimental-webgl");
            (data["gl"] = get_gl_infos(gl)), (data["gl2"] = get_gl_infos(gl2));
            data["gl_experimental"] = get_gl_infos(gl2);
        }

        return data;
    } else {
        return { status: "not chromium" };
    }
}

globalThis.fp_click_promise = new Promise((resolve, reject)=>{globalThis.fp_click_callback = resolve})

module.exports = getFingerprint;
