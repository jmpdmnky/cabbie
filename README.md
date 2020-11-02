# cabbie

{
    "dev": {
        "aws_profile": "dev-profile",
        "env":{}
    },
    "qa": {
        "aws_profile": "qa-profile",
        "env":{}
    },
    "prod": {
        "aws_profile": "prod-profile",
        "env":{}
    }
}


## Plugins:
external functions passed into a resource object to be added to build/modify/destroy queue
```
        "plugins" : {
            "export_api_endpoints": { # name the run of this plugin so it can be referred to later
                "pre": ["build", "modify"],  # what stages should this be run at the start of?
                "post": [], # what stages should this be run at the end of?
                "plugin": "eval_external_file", # the actual plugin name
                "options": "<path to file>",  # options to be passed into the plugin
                "priority": 0 # OPTIONAL: the plugins will be sorted by this number, ascending, when passed in
            },
            "build_website_code": {
                "pre": ["build", "modify"],
                "post": [],
                "plugin": "npm",
                "options": "run build",
                "priority": 1
            }
```