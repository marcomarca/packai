(function () {
  'use strict';

  var h = React.createElement;
  var numberFormat = new Intl.NumberFormat('es-BO');

  // Chromium may retain a hidden document offset after focusing a control during relayout.
  function resetDocumentScroll() {
    var scrollingElement = document.scrollingElement || document.documentElement;
    var root = document.getElementById('root');

    if (window.scrollX !== 0 || window.scrollY !== 0) window.scrollTo(0, 0);
    if (scrollingElement) {
      scrollingElement.scrollLeft = 0;
      scrollingElement.scrollTop = 0;
    }
    document.documentElement.scrollLeft = 0;
    document.documentElement.scrollTop = 0;
    if (document.body) {
      document.body.scrollLeft = 0;
      document.body.scrollTop = 0;
    }
    if (root) {
      root.scrollLeft = 0;
      root.scrollTop = 0;
    }
  }

  function apiReady() {
    return window.pywebview && window.pywebview.api;
  }

  function callApi(name, payload) {
    if (!apiReady()) {
      return Promise.reject(new Error('El puente de PyWebView todavía no está disponible.'));
    }
    if (typeof payload === 'undefined') {
      return window.pywebview.api[name]();
    }
    return window.pywebview.api[name](payload);
  }

  function canonicalize(paths) {
    var ordered = Array.from(new Set(paths)).sort(function (a, b) {
      var depth = a.split('/').length - b.split('/').length;
      return depth || a.localeCompare(b);
    });
    return ordered.filter(function (path, index) {
      return !ordered.slice(0, index).some(function (parent) {
        return path === parent || path.indexOf(parent + '/') === 0;
      });
    });
  }

  function excludingAncestor(path, exclusions) {
    var matches = exclusions.filter(function (candidate) {
      return path === candidate || path.indexOf(candidate + '/') === 0;
    });
    matches.sort(function (a, b) { return b.length - a.length; });
    return matches.length ? matches[0] : null;
  }

  function enabledChildren(node) {
    return (node.children || []).filter(function (child) { return !child.disabled; });
  }

  function selectionState(node, exclusions) {
    if (node.disabled) return 'disabled';
    if (excludingAncestor(node.path, exclusions)) return 'unchecked';
    var children = enabledChildren(node);
    if (!children.length) return 'checked';
    var states = children.map(function (child) { return selectionState(child, exclusions); });
    if (states.every(function (state) { return state === 'checked'; })) return 'checked';
    return 'partial';
  }

  function findNode(nodes, path) {
    for (var index = 0; index < nodes.length; index += 1) {
      var node = nodes[index];
      if (node.path === path) return node;
      var child = findNode(node.children || [], path);
      if (child) return child;
    }
    return null;
  }

  function addSiblingExclusions(node, targetPath, exclusions) {
    enabledChildren(node).forEach(function (child) {
      var onTargetBranch = targetPath === child.path || targetPath.indexOf(child.path + '/') === 0;
      if (onTargetBranch) {
        addSiblingExclusions(child, targetPath, exclusions);
      } else {
        exclusions.push(child.path);
      }
    });
  }

  function toggleExclusion(tree, node, exclusions) {
    var state = selectionState(node, exclusions);
    if (state === 'disabled') return exclusions;

    if (state === 'checked' || state === 'partial') {
      return canonicalize(
        exclusions.filter(function (path) {
          return path !== node.path && path.indexOf(node.path + '/') !== 0;
        }).concat([node.path])
      );
    }

    var next = exclusions.slice();
    var ancestor = excludingAncestor(node.path, next);
    if (ancestor && ancestor !== node.path) {
      next = next.filter(function (path) { return path !== ancestor; });
      var ancestorNode = findNode(tree, ancestor);
      if (ancestorNode) addSiblingExclusions(ancestorNode, node.path, next);
    }
    next = next.filter(function (path) {
      return path !== node.path && path.indexOf(node.path + '/') !== 0;
    });
    return canonicalize(next);
  }

  function filterTree(nodes, query) {
    if (!query) return nodes;
    var normalized = query.toLocaleLowerCase();
    return nodes.reduce(function (result, node) {
      var children = filterTree(node.children || [], query);
      var matches = node.name.toLocaleLowerCase().indexOf(normalized) >= 0 ||
        node.path.toLocaleLowerCase().indexOf(normalized) >= 0;
      if (matches || children.length) {
        result.push(Object.assign({}, node, { children: children }));
      }
      return result;
    }, []);
  }

  function findingCount(node, findings) {
    return findings.filter(function (finding) {
      return finding.relative_path.indexOf(node.path + '/') === 0;
    }).length;
  }

  function formatSize(bytes) {
    if (bytes === null || typeof bytes === 'undefined') return 'Pendiente';
    var units = ['B', 'KB', 'MB', 'GB'];
    var value = Number(bytes);
    var unit = units[0];
    for (var index = 0; index < units.length; index += 1) {
      unit = units[index];
      if (value < 1000 || index === units.length - 1) break;
      value /= 1000;
    }
    return unit === 'B' ? Math.round(value) + ' B' : value.toFixed(1) + ' ' + unit;
  }

  function Checkbox(props) {
    return h('input', {
      type: 'checkbox',
      checked: props.state === 'checked',
      disabled: props.state === 'disabled' || props.disabled,
      ref: function (element) {
        if (element) element.indeterminate = props.state === 'partial';
      },
      onChange: props.onChange,
      'aria-label': props.label
    });
  }

  function FolderRow(props) {
    var node = props.node;
    var state = selectionState(node, props.exclusions);
    var expanded = Boolean(props.expanded[node.path]) || Boolean(props.filter);
    var hasChildren = node.children && node.children.length > 0;
    var warnings = findingCount(node, props.findings);

    return h('div', { className: 'tree-branch' },
      h('div', {
        className: 'folder-row ' + (node.disabled ? 'folder-disabled' : ''),
        style: { paddingLeft: (12 + props.depth * 20) + 'px' },
        title: node.disabled_reason || node.path
      },
        h('button', {
          className: 'tree-chevron ' + (hasChildren ? '' : 'invisible'),
          onClick: function () { props.onExpand(node.path); },
          type: 'button',
          'aria-label': expanded ? 'Contraer carpeta' : 'Expandir carpeta'
        }, expanded ? '⌄' : '›'),
        h(Checkbox, {
          state: state,
          label: 'Incluir ' + node.path,
          disabled: props.locked,
          onChange: function () { if (!props.locked) props.onToggle(node); }
        }),
        h('span', { className: 'folder-icon' }, node.disabled ? '🔒' : '📁'),
        h('span', { className: 'folder-name' }, node.name),
        node.disabled ? null : h('span', { className: 'folder-meta' },
          node.direct_file_count ? h('span', { className: 'file-count' }, node.direct_file_count + ' archivos') : null,
          h('span', {
            className: 'folder-size',
            title: 'Tamaño recursivo en disco; no incluye carpetas bloqueadas'
          }, formatSize(node.total_size_bytes || 0))
        ),
        warnings ? h('span', { className: 'warning-pill' }, warnings + ' alertas') : null,
        node.disabled_reason ? h('span', { className: 'policy-reason' }, node.disabled_reason) : null
      ),
      expanded && hasChildren ? h('div', null,
        node.children.map(function (child) {
          return h(FolderRow, Object.assign({}, props, {
            key: child.path,
            node: child,
            depth: props.depth + 1
          }));
        })
      ) : null
    );
  }

  function MetricCard(props) {
    return h('div', { className: 'metric-card' },
      h('span', { className: 'metric-label' }, props.label),
      h('strong', { className: 'metric-value' }, props.value),
      props.detail ? h('span', { className: 'metric-detail' }, props.detail) : null
    );
  }

  function Toggle(props) {
    return h('label', { className: 'toggle-control ' + (props.disabled ? 'control-disabled' : '') },
      h('input', {
        type: 'checkbox',
        checked: props.checked,
        disabled: props.disabled,
        onChange: function (event) { props.onChange(event.target.checked); }
      }),
      h('span', { className: 'toggle-track' }, h('span', { className: 'toggle-thumb' })),
      h('span', { className: 'toggle-copy' },
        h('strong', null, props.label),
        props.help ? h('small', null, props.help) : null
      )
    );
  }

  function CommandBox(props) {
    return h('div', { className: 'command-box' },
      h('div', { className: 'command-label' }, props.label),
      h('code', null, props.command || '—'),
      h('button', {
        type: 'button',
        className: 'icon-button',
        onClick: function () { props.onCopy(props.command); },
        disabled: !props.command
      }, 'Copiar')
    );
  }

  function ErrorBanner(props) {
    if (!props.error) return null;
    return h('div', { className: 'error-banner' },
      h('div', null,
        h('strong', null, props.error.title || 'Error'),
        h('p', null, props.error.message || String(props.error)),
        props.error.resolution ? h('small', null, props.error.resolution) : null
      ),
      h('button', { type: 'button', onClick: props.onClose }, 'Cerrar')
    );
  }

  function emptyPreview() {
    return { metrics: null, findings: [], warnings: [] };
  }

  function payloadFromState(state) {
    return {
      exclude_paths: state.exclusions,
      force: state.options.force,
      include_git_context: state.options.include_git_context,
      include_env_example: state.options.include_env_example,
      include_lockfiles: state.options.include_lockfiles,
      token_top: Number(state.options.token_top),
      copy_mode: state.options.copy_mode
    };
  }

  function App() {
    React.Component.apply(this, arguments);
    this.state = {
      initialized: false,
      loading: true,
      calculating: false,
      packing: false,
      stale: false,
      root: '',
      projectName: '',
      tree: [],
      exclusions: [],
      options: {
        force: false,
        include_git_context: false,
        include_env_example: true,
        include_lockfiles: true,
        token_top: 3,
        copy_mode: 'file'
      },
      preview: emptyPreview(),
      commands: { pack: '', gui: '' },
      expanded: {},
      filter: '',
      monitorMode: 'iniciando',
      notice: '',
      outputZip: '',
      error: null
    };
    this.previewTimer = null;
    this.refreshTimer = null;
    this.requestSerial = 0;
    this.filesystemRevision = 0;
    this.viewportFrame = null;
    this.viewportGuard = this.stabilizeViewport.bind(this);
    this.visualViewport = null;
    this.revealActiveOption = false;
  }

  App.prototype = Object.create(React.Component.prototype);
  App.prototype.constructor = App;

  App.prototype.componentDidMount = function () {
    var self = this;
    window.__packaiApp = this;
    window.addEventListener('scroll', this.viewportGuard, false);
    window.addEventListener('resize', this.viewportGuard, false);
    document.addEventListener('focusin', this.viewportGuard, true);
    this.visualViewport = window.visualViewport || null;
    if (this.visualViewport) {
      this.visualViewport.addEventListener('scroll', this.viewportGuard, false);
      this.visualViewport.addEventListener('resize', this.viewportGuard, false);
    }
    this.stabilizeViewport();
    window.packaiFilesystemChanged = function () { self.onFilesystemChanged(); };
    window.packaiMonitorReady = function (payload) {
      self.setState({ monitorMode: payload.mode === 'events' ? 'eventos' : 'sondeo eficiente' });
    };
    if (apiReady()) {
      this.initialize();
    } else {
      window.addEventListener('pywebviewready', function () { self.initialize(); }, { once: true });
    }
  };

  App.prototype.componentDidUpdate = function () {
    this.stabilizeViewport();
  };

  App.prototype.componentWillUnmount = function () {
    if (this.previewTimer) window.clearTimeout(this.previewTimer);
    if (this.refreshTimer) window.clearTimeout(this.refreshTimer);
    if (this.viewportFrame !== null) window.cancelAnimationFrame(this.viewportFrame);
    window.removeEventListener('scroll', this.viewportGuard, false);
    window.removeEventListener('resize', this.viewportGuard, false);
    document.removeEventListener('focusin', this.viewportGuard, true);
    if (this.visualViewport) {
      this.visualViewport.removeEventListener('scroll', this.viewportGuard, false);
      this.visualViewport.removeEventListener('resize', this.viewportGuard, false);
    }
  };

  App.prototype.stabilizeViewport = function () {
    var self = this;
    resetDocumentScroll();
    if (this.viewportFrame !== null) window.cancelAnimationFrame(this.viewportFrame);
    this.viewportFrame = window.requestAnimationFrame(function () {
      resetDocumentScroll();
      self.viewportFrame = null;
    });
  };

  // Metrics above the options panel can grow or shrink while the selected control keeps focus.
  App.prototype.keepFocusedOptionVisible = function () {
    if (!this.revealActiveOption) return;
    this.revealActiveOption = false;

    var active = document.activeElement;
    var optionsPanel = document.querySelector('.options-panel');
    if (!active || !optionsPanel || !optionsPanel.contains(active)) return;

    var self = this;
    var control = active.closest('.toggle-control, .field-row');
    if (!control) return;
    window.requestAnimationFrame(function () {
      control.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      self.stabilizeViewport();
    });
  };

  App.prototype.initialize = function () {
    var self = this;
    this.setState({ loading: true, error: null });
    callApi('initialize').then(function (response) {
      if (!response.ok) return self.handleError(response.error);
      var expanded = {};
      (response.tree || []).forEach(function (node) { expanded[node.path] = true; });
      self.setState({
        initialized: true,
        loading: false,
        root: response.root,
        projectName: response.project_name,
        tree: response.tree || [],
        exclusions: response.excluded_paths || [],
        options: response.options,
        preview: response.preview || emptyPreview(),
        commands: response.commands || { pack: '', gui: '' },
        expanded: expanded,
        error: null
      });
    }).catch(function (error) { self.handleError({ title: 'No se pudo iniciar', message: error.message }); });
  };

  App.prototype.handleError = function (error) {
    this.setState({
      loading: false,
      calculating: false,
      packing: false,
      error: error || { title: 'Error', message: 'Operación fallida.' }
    });
  };

  App.prototype.onFilesystemChanged = function () {
    var self = this;
    this.filesystemRevision += 1;
    this.setState({ stale: true, notice: 'Se detectaron cambios en el proyecto.' });
    if (this.refreshTimer) window.clearTimeout(this.refreshTimer);
    if (this.state.packing) return;
    this.refreshTimer = window.setTimeout(function () { self.refresh(); }, 700);
  };

  App.prototype.refresh = function () {
    var self = this;
    if (this.previewTimer) {
      window.clearTimeout(this.previewTimer);
      this.previewTimer = null;
    }
    var serial = ++this.requestSerial;
    this.setState({ calculating: true, stale: true, error: null });
    callApi('refresh', payloadFromState(this.state)).then(function (response) {
      if (serial !== self.requestSerial) return;
      if (!response.ok) return self.handleError(response.error);
      self.setState({
        calculating: false,
        stale: false,
        tree: response.tree || [],
        exclusions: response.excluded_paths || [],
        options: response.options,
        preview: response.preview || emptyPreview(),
        commands: response.commands || self.state.commands,
        notice: 'Proyecto actualizado.'
      });
    }).catch(function (error) { self.handleError({ title: 'Error al actualizar', message: error.message }); });
  };

  App.prototype.schedulePreview = function () {
    var self = this;
    this.requestSerial += 1;
    if (this.previewTimer) window.clearTimeout(this.previewTimer);
    this.setState({ calculating: true });
    this.previewTimer = window.setTimeout(function () { self.preview(); }, 420);
  };

  App.prototype.preview = function () {
    var self = this;
    var serial = ++this.requestSerial;
    callApi('preview', payloadFromState(this.state)).then(function (response) {
      if (serial !== self.requestSerial) return;
      if (!response.ok) return self.handleError(response.error);
      self.setState({
        calculating: false,
        exclusions: response.excluded_paths || self.state.exclusions,
        options: response.options,
        preview: response.preview || emptyPreview(),
        commands: response.commands || self.state.commands
      }, function () { self.keepFocusedOptionVisible(); });
    }).catch(function (error) { self.handleError({ title: 'Error al calcular métricas', message: error.message }); });
  };

  App.prototype.toggleFolder = function (node) {
    if (this.state.packing) return;
    var next = toggleExclusion(this.state.tree, node, this.state.exclusions);
    this.setState({ exclusions: next, notice: '' }, this.schedulePreview.bind(this));
  };

  App.prototype.toggleExpanded = function (path) {
    var expanded = Object.assign({}, this.state.expanded);
    expanded[path] = !expanded[path];
    this.setState({ expanded: expanded });
  };

  App.prototype.setOption = function (key, value) {
    if (this.state.packing) return;
    var options = Object.assign({}, this.state.options);
    options[key] = value;
    this.revealActiveOption = true;
    this.setState({ options: options, notice: '' }, this.schedulePreview.bind(this));
  };

  App.prototype.generate = function () {
    var self = this;
    if (this.state.packing || !this.state.initialized) return;
    if (this.previewTimer) {
      window.clearTimeout(this.previewTimer);
      this.previewTimer = null;
    }
    if (this.refreshTimer) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
    var serial = ++this.requestSerial;
    var filesystemRevision = this.filesystemRevision;
    this.setState({
      packing: true, calculating: false,
      notice: 'Reescaneando y generando el ZIP…', error: null
    });
    callApi('pack', payloadFromState(this.state)).then(function (response) {
      if (serial !== self.requestSerial) return;
      if (!response.ok) return self.handleError(response.error);
      var changedDuringPack = filesystemRevision !== self.filesystemRevision;
      self.setState({
        packing: false,
        stale: changedDuringPack,
        tree: response.tree || self.state.tree,
        exclusions: response.excluded_paths || self.state.exclusions,
        options: response.options,
        preview: response.preview || emptyPreview(),
        commands: response.commands || self.state.commands,
        outputZip: response.output_zip || '',
        notice: changedDuringPack
          ? 'ZIP generado; actualizando cambios detectados durante la generación…'
          : (response.copy_message || 'ZIP generado.')
      }, function () {
        if (changedDuringPack) self.refresh();
      });
    }).catch(function (error) { self.handleError({ title: 'Error al generar', message: error.message }); });
  };

  App.prototype.copyCommand = function (command) {
    var self = this;
    if (!command) return;
    var nativeCopy = navigator.clipboard && navigator.clipboard.writeText
      ? navigator.clipboard.writeText(command)
      : Promise.reject(new Error('Clipboard API no disponible'));
    nativeCopy.then(function () {
      self.setState({ notice: 'Comando copiado.' });
    }).catch(function () {
      callApi('copy_command', command).then(function (response) {
        if (response.ok) self.setState({ notice: 'Comando copiado.' });
        else self.handleError(response.error);
      });
    });
  };

  App.prototype.renderMetrics = function () {
    var preview = this.state.preview || emptyPreview();
    var metrics = preview.metrics;
    if (!metrics) {
      return h('div', { className: 'empty-state' },
        h('strong', null, this.state.calculating ? 'Calculando métricas…' : 'Métricas no disponibles'),
        h('p', null, 'El empaquetado seguirá funcionando aunque el cálculo informativo falle.')
      );
    }
    return h('div', null,
      h('div', { className: 'metrics-grid' },
        h(MetricCard, { label: 'Tokens estimados', value: numberFormat.format(metrics.estimated_tokens), detail: metrics.tokenizer }),
        h(MetricCard, { label: 'Archivos incluidos', value: numberFormat.format(metrics.included_files), detail: metrics.text_files + ' texto · ' + metrics.binary_files + ' binarios' }),
        h(MetricCard, { label: 'Líneas de código', value: numberFormat.format(metrics.code_lines || 0), detail: numberFormat.format(metrics.code_files || 0) + ' archivos de código' }),
        h(MetricCard, { label: 'Sin comprimir', value: formatSize(metrics.uncompressed_size), detail: 'Contenido seleccionado' }),
        h(MetricCard, { label: 'ZIP', value: formatSize(metrics.zip_size), detail: metrics.zip_size === null ? 'Disponible después de generar' : 'Última generación' })
      ),
      metrics.degraded ? h('div', { className: 'inline-warning' }, 'Estimación degradada mediante ' + metrics.tokenizer) : null,
      metrics.language_code_lines && metrics.language_code_lines.length
        ? h('div', null,
            h('div', { className: 'section-heading' },
              h('h3', null, 'Líneas por lenguaje'),
              h('span', null, metrics.language_code_lines.length + ' lenguajes')
            ),
            h('div', { className: 'token-list' }, metrics.language_code_lines.slice(0, 12).map(function (item, index) {
              return h('div', { className: 'token-row', key: item.language },
                h('span', { className: 'rank' }, index + 1),
                h('span', { className: 'token-path', title: item.files + ' archivos' }, item.language),
                h('strong', null, numberFormat.format(item.code_lines))
              );
            }))
          )
        : null,
      h('div', { className: 'section-heading' },
        h('h3', null, 'Archivos con más tokens'),
        h('span', null, 'Top ' + this.state.options.token_top)
      ),
      metrics.largest_token_files && metrics.largest_token_files.length
        ? h('div', { className: 'token-list' }, metrics.largest_token_files.map(function (item, index) {
            return h('div', { className: 'token-row', key: item.relative_path },
              h('span', { className: 'rank' }, index + 1),
              h('span', { className: 'token-path', title: item.relative_path }, item.relative_path),
              h('strong', null, numberFormat.format(item.token_count))
            );
          }))
        : h('p', { className: 'muted' }, 'No hay archivos textuales en el ranking.')
    );
  };

  App.prototype.renderAlerts = function () {
    var preview = this.state.preview || emptyPreview();
    var findings = preview.findings || [];
    var warnings = preview.warnings || [];
    if (!findings.length && !warnings.length) return null;
    return h('div', { className: 'alerts-panel' },
      h('div', { className: 'section-heading' }, h('h3', null, 'Alertas'), h('span', null, findings.length + warnings.length)),
      findings.slice(0, 8).map(function (finding) {
        return h('div', { className: 'alert-row', key: finding.relative_path },
          h('span', null, finding.forced ? '⚠️' : '⛔'),
          h('div', null,
            h('strong', null, finding.relative_path),
            h('small', null, finding.forced ? 'Incluido por Force' : 'Excluido por seguridad')
          )
        );
      }),
      warnings.slice(0, 5).map(function (warning, index) {
        return h('div', { className: 'alert-row', key: 'warning-' + index }, h('span', null, '⚠️'), h('small', null, warning));
      })
    );
  };

  App.prototype.render = function () {
    if (!this.state.initialized && this.state.loading) {
      return h('div', { className: 'boot' }, h('div', { className: 'spinner' }), 'Iniciando Pack AI…');
    }

    var self = this;
    var filteredTree = filterTree(this.state.tree, this.state.filter);
    var findings = (this.state.preview && this.state.preview.findings) || [];
    var busy = this.state.loading || this.state.calculating || this.state.packing;
    var locked = this.state.packing || !this.state.initialized;
    var generateLabel = this.state.options.copy_mode === 'file'
      ? 'Generar ZIP y copiar'
      : this.state.options.copy_mode === 'path'
        ? 'Generar ZIP y copiar ruta'
        : 'Generar ZIP';

    return h('div', { className: 'app-shell' },
      h('header', { className: 'topbar' },
        h('div', { className: 'brand' },
          h('div', { className: 'brand-mark' }, 'AI'),
          h('div', null, h('h1', null, 'Pack AI'), h('p', null, this.state.projectName || 'Proyecto'))
        ),
        h('div', { className: 'project-path', title: this.state.root }, this.state.root),
        h('div', { className: 'status-cluster' },
          h('span', { className: 'status-dot ' + (this.state.stale ? 'stale' : 'ready') }),
          h('span', null, this.state.stale ? 'Cambios pendientes' : 'Sincronizado'),
          h('span', { className: 'monitor-badge' }, this.state.monitorMode)
        )
      ),
      h(ErrorBanner, {
        error: this.state.error,
        onClose: function () { self.setState({ error: null }); }
      }),
      h('main', { className: 'workspace' },
        h('section', { className: 'tree-panel panel' },
          h('div', { className: 'panel-header' },
            h('div', null, h('h2', null, 'Carpetas del proyecto'), h('p', null, 'Tamaños recursivos en disco; las rutas bloqueadas no se miden.')),
            h('button', { type: 'button', className: 'secondary-button', onClick: this.refresh.bind(this), disabled: busy }, this.state.calculating ? 'Actualizando…' : 'Actualizar')
          ),
          h('div', { className: 'search-wrap' },
            h('span', null, '⌕'),
            h('input', {
              type: 'search',
              value: this.state.filter,
              placeholder: 'Buscar carpeta…',
              onChange: function (event) { self.setState({ filter: event.target.value }); }
            }),
            this.state.exclusions.length ? h('span', { className: 'selection-count' }, this.state.exclusions.length + ' exclusiones') : null
          ),
          h('div', { className: 'tree-scroll' },
            filteredTree.length
              ? filteredTree.map(function (node) {
                  return h(FolderRow, {
                    key: node.path,
                    node: node,
                    depth: 0,
                    exclusions: self.state.exclusions,
                    expanded: self.state.expanded,
                    findings: findings,
                    filter: self.state.filter,
                    locked: locked,
                    onExpand: self.toggleExpanded.bind(self),
                    onToggle: self.toggleFolder.bind(self)
                  });
                })
              : h('div', { className: 'empty-state' }, 'No hay carpetas que coincidan.')
          )
        ),
        h('aside', { className: 'side-panel' },
          h('section', { className: 'panel stats-panel' },
            h('div', { className: 'panel-header compact' },
              h('div', null, h('h2', null, 'Vista previa'), h('p', null, this.state.calculating ? 'Calculando sobre el estado actual…' : 'Contenido que entrará en el próximo ZIP.')),
              this.state.calculating ? h('div', { className: 'mini-spinner' }) : null
            ),
            this.renderMetrics()
          ),
          this.renderAlerts(),
          h('section', { className: 'panel options-panel' },
            h('div', { className: 'section-heading' }, h('h3', null, 'Opciones')),
            h(Toggle, {
              checked: this.state.options.force,
              label: 'Force',
              help: 'Incluye archivos con alertas de secretos; no desbloquea ejecutables ni .env.',
              disabled: locked,
              onChange: function (value) { self.setOption('force', value); }
            }),
            h(Toggle, {
              checked: this.state.options.include_git_context,
              label: 'Contexto Git',
              help: 'Añade el diff del último commit y lo cuenta en las métricas.',
              disabled: locked,
              onChange: function (value) { self.setOption('include_git_context', value); }
            }),
            h(Toggle, {
              checked: this.state.options.include_env_example,
              label: 'Incluir ejemplos .env',
              help: 'Los ejemplos se escanean antes de incluirse.',
              disabled: locked,
              onChange: function (value) { self.setOption('include_env_example', value); }
            }),
            h(Toggle, {
              checked: this.state.options.include_lockfiles,
              label: 'Incluir lockfiles',
              help: 'Incluye uv.lock, bun.lock, package-lock.json y lockfiles conocidos.',
              disabled: locked,
              onChange: function (value) { self.setOption('include_lockfiles', value); }
            }),
            h('div', { className: 'field-row' },
              h('label', null, 'Ranking de tokens'),
              h('input', {
                type: 'number', min: 0, max: 100,
                disabled: locked,
                value: this.state.options.token_top,
                onChange: function (event) { self.setOption('token_top', Math.max(0, Math.min(100, Number(event.target.value) || 0))); }
              })
            ),
            h('div', { className: 'field-row' },
              h('label', null, 'Después de generar'),
              h('select', {
                value: this.state.options.copy_mode,
                disabled: locked,
                onChange: function (event) { self.setOption('copy_mode', event.target.value); }
              },
                h('option', { value: 'file' }, 'Copiar archivo ZIP'),
                h('option', { value: 'path' }, 'Copiar ruta'),
                h('option', { value: 'none' }, 'No copiar')
              )
            )
          )
        )
      ),
      h('footer', { className: 'action-dock' },
        h('div', { className: 'commands' },
          h(CommandBox, { label: 'Repetir desde CLI', command: this.state.commands.pack, onCopy: this.copyCommand.bind(this) }),
          h(CommandBox, { label: 'Reabrir esta selección', command: this.state.commands.gui, onCopy: this.copyCommand.bind(this) })
        ),
        h('div', { className: 'primary-actions' },
          this.state.notice ? h('div', { className: 'notice', title: this.state.outputZip }, this.state.notice) : null,
          h('button', {
            type: 'button',
            className: 'primary-button',
            disabled: locked,
            onClick: this.generate.bind(this)
          }, this.state.packing ? 'Generando…' : generateLabel)
        )
      )
    );
  };

  ReactDOM.createRoot(document.getElementById('root')).render(h(App));
}());
