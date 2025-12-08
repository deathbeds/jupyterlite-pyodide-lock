# 🕹️ DEMO

```{hint}
Pick one of the demos above to show it here.
```

<ul id="jlpl-demo-choices">
  <li>
    <form target="jlpm-demo-iframe" action="./_static/lab/">
      <input type="hidden" name="path" value="CHANGELOG.md" />
      <input type="hidden" name="path" value="README.md" />
      <input type="hidden" name="path" value="README.ipynb" />
      <button class="btn btn-info" type="submit" title="show a demo with a multiple documents">
        <i class="fas fa-flask"></i> Lab
      </button>
    </form>
  </li>
  <li>
    <form target="jlpm-demo-iframe" action="./_static/notebooks/">
      <input type="hidden" name="path" value="README.ipynb" />
      <button class="btn btn-info" type="submit" title="show a demo with a single document">
        <i class="fas fa-book"></i> Notebook
      </button>
    </form>
  </li>
  <li>
    <form target="jlpm-demo-iframe" action="./_static/repl">
      <input type="hidden" name="kernel" value="python" />
      <input type="hidden" name="toolbar" value="1" />
      <input type="hidden" name="showBanner" value="1" />
      <input type="hidden" name="promptCellPosition" value="left">
      <input type="hidden" name="code" value="from ipywidgets import *; (x := FloatSlider(description='x'))">
      <button class="btn btn-info" type="submit" title="show a read-execute-print loop app">
        <i class="fas fa-code"></i> REPL
      </button>
    </form>
  </li>
  <li>
    <form target="jlpm-demo-iframe" action="./_static/voici/render/README.html">
      <button class="btn btn-info" type="submit" title="show a notebook as an app">
        <i class="fas fa-gamepad"></i> Voici
      </button>
    </form>
  </li>
</ul>

<div class="jlpl-demo">
  <iframe src="about:blank" width="100%" id="jlpm-demo-iframe" name="jlpm-demo-iframe"></iframe>
</div>
