function show_json(json){
    $('#json-renderer').jsonViewer(json,{collapsed: true, withQuotes: false, withLinks: false});
}

async function show_fp(){
    while(true){
        json = await collect_fingerprint(document.querySelector("#get-fp"))
        show_json(json)
        document.querySelector("#json-renderer > ul").style.display = ""
    }
}