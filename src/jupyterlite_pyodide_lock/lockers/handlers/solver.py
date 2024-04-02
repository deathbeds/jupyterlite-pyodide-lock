from typing import TYPE_CHECKING

import jinja2
from tornado.web import RequestHandler

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger



class SolverHTML(RequestHandler):
    context: dict
    log: "Logger"

    def initialize(self, context, *args, **kwargs):
        log = kwargs.pop("log")
        super().initialize(*args, **kwargs)
        self.context = context
        self.log = log

    async def get(self, *args, **kwargs):
        template = jinja2.Template(self.TEMPLATE)
        rendered = template.render(self.context)
        self.log.debug("Serving HTML\n%s", rendered)
        await self.finish(rendered)

    TEMPLATE = """
        <html>
            <script type="module">
                import { loadPyodide } from './static/pyodide/pyodide.mjs';

                async function post(url, body) {
                    return await fetch(
                        url, {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body
                    });
                }

                function tee(pipe, message) {
                    console.log(pipe, message);
                    void post(`/log/${pipe}`, JSON.stringify({ message }, null, 2));
                    const pre = document.window.createElement('pre');
                    pre.textContent = message;
                    document.body.appendChild(pre);
                }

                const pyodide = await loadPyodide({
                    stdout: tee.bind(this, 'stdout'),
                    stderr: tee.bind(this, 'stderr'),
                    packages: ["micropip"],
                });

                await pyodide.runPythonAsync(`
                    try:
                        import micropip, js, json
                        await micropip.install(
                            **json.loads(
                                '''
                                {{ micropip_args_json }}
                                '''
                            )
                        )
                        js.window.PYODIDE_LOCK = micropip.freeze()
                    except Exception as err:
                        js.window.PYODIDE_ERROR = str(err)
                `);

                await post(
                    "./pyodide-lock.json",
                    window.PYODIDE_LOCK
                        || JSON.stringify({"error": window.PYODIDE_ERROR})
                );
                window.close();
            </script>
        </html>
    """
