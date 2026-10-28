/* StudyShare dashboard + AI chat interactions */
(function () {
  "use strict";

  var app = document.getElementById("ssApp");
  if (!app) {
    return;
  }

  var COLLAPSE_KEY = "studyshare-sidebar-collapsed";
  var PROMO_KEY = "studyshare-promo-dismissed";
  var toastEl = document.getElementById("ssToast");
  var toastTimer = null;

  function showToast(message) {
    if (!toastEl) {
      return;
    }
    toastEl.textContent = message;
    toastEl.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toastEl.classList.remove("is-visible");
    }, 2600);
  }

  /* ------------------------------------------------------------ sidebar */

  var collapseBtn = document.querySelector("[data-ss-collapse]");

  function setCollapsed(collapsed) {
    app.classList.toggle("is-collapsed", collapsed);
    if (collapseBtn) {
      collapseBtn.setAttribute("aria-expanded", String(!collapsed));
      collapseBtn.setAttribute("title", collapsed ? "Expand sidebar" : "Collapse sidebar");
      collapseBtn.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
    }
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch (error) {
      /* Storage can be unavailable in private mode. */
    }
  }

  if (collapseBtn) {
    var savedCollapsed = false;
    try {
      savedCollapsed = window.localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch (error) {
      savedCollapsed = false;
    }
    if (savedCollapsed) {
      app.classList.add("is-collapsed");
      collapseBtn.setAttribute("aria-expanded", "false");
      collapseBtn.setAttribute("title", "Expand sidebar");
      collapseBtn.setAttribute("aria-label", "Expand sidebar");
    }

    collapseBtn.addEventListener("click", function () {
      setCollapsed(!app.classList.contains("is-collapsed"));
    });
  }

  var mobileToggles = document.querySelectorAll("[data-ss-mobile-toggle]");
  var mobileQuery = window.matchMedia("(max-width: 1023.98px)");

  function setMobileOpen(open) {
    app.classList.toggle("is-mobile-open", open);
    document.body.style.overflow = open ? "hidden" : "";
    mobileToggles.forEach(function (toggle) {
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  mobileToggles.forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var isBackdrop = toggle.classList.contains("ss-backdrop");
      setMobileOpen(isBackdrop ? false : !app.classList.contains("is-mobile-open"));
    });
  });

  if (mobileQuery.addEventListener) {
    mobileQuery.addEventListener("change", function (event) {
      if (!event.matches) {
        setMobileOpen(false);
      }
    });
  }

  document.querySelectorAll("#ssSidebar a").forEach(function (link) {
    link.addEventListener("click", function () {
      if (mobileQuery.matches) {
        setMobileOpen(false);
      }
    });
  });

  /* -------------------------------------------------------- profile menu */

  var profileBtn = document.getElementById("ssProfileBtn");
  var profileMenu = document.getElementById("ssProfileMenu");

  function setProfileMenu(open) {
    if (!profileMenu || !profileBtn) {
      return;
    }
    profileMenu.classList.toggle("is-open", open);
    profileMenu.setAttribute("aria-hidden", String(!open));
    profileBtn.setAttribute("aria-expanded", String(open));
  }

  if (profileBtn && profileMenu) {
    profileBtn.addEventListener("click", function (event) {
      event.stopPropagation();
      setProfileMenu(!profileMenu.classList.contains("is-open"));
    });

    document.addEventListener("click", function (event) {
      if (!profileMenu.classList.contains("is-open")) {
        return;
      }
      if (!profileMenu.contains(event.target) && !profileBtn.contains(event.target)) {
        setProfileMenu(false);
      }
    });
  }

  /* --------------------------------------------------------- offer dialog */

  var offerDialog = document.getElementById("ssOfferDialog");

  function openOffer() {
    if (mobileQuery.matches) {
      setMobileOpen(false);
    }
    if (offerDialog && typeof offerDialog.showModal === "function") {
      offerDialog.showModal();
    } else {
      showToast("StudyShare is free for every student account.");
    }
  }

  document.querySelectorAll("[data-ss-offer]").forEach(function (button) {
    button.addEventListener("click", openOffer);
  });

  document.querySelectorAll("[data-ss-dialog-close]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (offerDialog) {
        offerDialog.close();
      }
    });
  });

  if (offerDialog) {
    offerDialog.addEventListener("click", function (event) {
      if (event.target === offerDialog) {
        offerDialog.close();
      }
    });
  }

  /* ------------------------------------------------------------- promo */

  var promo = document.getElementById("ssPromo");
  var promoClose = document.querySelector("[data-ss-promo-close]");

  if (promo) {
    try {
      if (window.localStorage.getItem(PROMO_KEY) === "1") {
        promo.hidden = true;
      }
    } catch (error) {
      /* Ignore storage errors. */
    }
  }

  if (promo && promoClose) {
    promoClose.addEventListener("click", function () {
      promo.classList.add("is-hiding");
      try {
        window.localStorage.setItem(PROMO_KEY, "1");
      } catch (error) {
        /* Ignore storage errors. */
      }
      window.setTimeout(function () {
        promo.hidden = true;
      }, 180);
    });
  }

  /* ------------------------------------------------------------- markdown */

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderInline(value) {
    var codes = [];
    var text = value.replace(/`([^`]+)`/g, function (match, code) {
      codes.push(code);
      return "\u0000" + (codes.length - 1) + "\u0000";
    });

    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*)\)/g, function (match, label, href) {
      var external = href.indexOf("http") === 0 ? ' target="_blank" rel="noopener noreferrer"' : "";
      return '<a href="' + href + '"' + external + ">" + label + "</a>";
    });
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    text = text.replace(/\u0000(\d+)\u0000/g, function (match, index) {
      return "<code>" + codes[Number(index)] + "</code>";
    });
    return text;
  }

  function renderMarkdown(value) {
    var source = String(value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    var lines = source.split("\n");
    var html = [];
    var paragraph = [];
    var listType = null;
    var inCode = false;
    var codeLines = [];

    function flushParagraph() {
      if (!paragraph.length) {
        return;
      }
      html.push(
        "<p>" +
          paragraph
            .map(function (line) {
              return renderInline(escapeHtml(line));
            })
            .join("<br>") +
          "</p>"
      );
      paragraph = [];
    }

    function closeList() {
      if (listType) {
        html.push("</" + listType + ">");
        listType = null;
      }
    }

    function openList(type) {
      if (listType !== type) {
        closeList();
        html.push("<" + type + ">");
        listType = type;
      }
    }

    lines.forEach(function (line) {
      if (/^```/.test(line)) {
        if (inCode) {
          html.push("<pre><code>" + escapeHtml(codeLines.join("\n")) + "</code></pre>");
          codeLines = [];
          inCode = false;
        } else {
          flushParagraph();
          closeList();
          inCode = true;
        }
        return;
      }

      if (inCode) {
        codeLines.push(line);
        return;
      }

      if (!line.trim()) {
        flushParagraph();
        closeList();
        return;
      }

      var heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        closeList();
        var level = heading[1].length;
        html.push(
          "<h" + level + ">" + renderInline(escapeHtml(heading[2])) + "</h" + level + ">"
        );
        return;
      }

      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
        flushParagraph();
        closeList();
        html.push("<hr>");
        return;
      }

      var quote = line.match(/^>\s?(.*)$/);
      if (quote) {
        flushParagraph();
        closeList();
        html.push("<blockquote>" + renderInline(escapeHtml(quote[1])) + "</blockquote>");
        return;
      }

      var bullet = line.match(/^\s*[-*•]\s+(.+)$/);
      if (bullet) {
        flushParagraph();
        openList("ul");
        html.push("<li>" + renderInline(escapeHtml(bullet[1])) + "</li>");
        return;
      }

      var numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
      if (numbered) {
        flushParagraph();
        openList("ol");
        html.push("<li>" + renderInline(escapeHtml(numbered[1])) + "</li>");
        return;
      }

      closeList();
      paragraph.push(line);
    });

    if (inCode && codeLines.length) {
      html.push("<pre><code>" + escapeHtml(codeLines.join("\n")) + "</code></pre>");
    }
    flushParagraph();
    closeList();
    return html.join("");
  }

  function enhanceMarkdown(root) {
    (root || document).querySelectorAll("[data-markdown]:not(.is-rendered)").forEach(function (element) {
      element.innerHTML = renderMarkdown(element.textContent || "");
      element.classList.add("is-rendered");
    });
  }

  enhanceMarkdown(document);

  /* --------------------------------------------------------- copy answer */

  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest("[data-ss-copy]") : null;
    if (!button) {
      return;
    }
    var message = button.closest(".ss-msg");
    var body = message ? message.querySelector("[data-markdown]") : null;
    var text = body ? body.textContent : "";
    if (!text) {
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          showToast("Copied to clipboard.");
        })
        .catch(function () {
          showToast("Could not copy this answer.");
        });
    } else {
      showToast("Copy is not supported in this browser.");
    }
  });

  /* ------------------------------------------------------ prompt composer */

  var promptForm = document.getElementById("ssPromptForm");
  var promptInput = document.getElementById("ssPromptInput");

  function setPromptBusy(busy) {
    if (promptInput) {
      promptInput.disabled = busy;
    }
    if (promptForm) {
      var send = promptForm.querySelector(".ss-send");
      if (send) {
        send.disabled = busy;
        send.classList.toggle("is-loading", busy);
      }
    }
  }

  if (promptForm && promptInput) {
    promptForm.addEventListener("submit", function (event) {
      if (!promptInput.value.trim()) {
        event.preventDefault();
        promptInput.focus();
        return;
      }
      if (!window.fetch || !window.FormData) {
        return;
      }

      event.preventDefault();
      var formData = new FormData(promptForm);
      setPromptBusy(true);

      fetch(promptForm.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        body: formData,
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { response: response, data: data };
          });
        })
        .then(function (result) {
          if (!result.response.ok || !result.data.ok) {
            throw new Error(result.data.error || "Could not start the chat.");
          }
          window.location.href = result.data.redirect_url;
        })
        .catch(function (error) {
          setPromptBusy(false);
          showToast(error.message || "Could not start the chat.");
        });
    });
  }

  document.querySelectorAll("[data-ss-prefill]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!promptInput) {
        return;
      }
      promptInput.value = button.getAttribute("data-ss-prefill") || "";
      promptInput.focus();
      promptInput.setSelectionRange(promptInput.value.length, promptInput.value.length);
    });
  });

  var searchToggle = document.querySelector("[data-ss-search-toggle]");
  if (searchToggle) {
    searchToggle.addEventListener("click", function () {
      if (mobileQuery.matches) {
        setMobileOpen(false);
      }
      var target =
        promptInput ||
        document.getElementById("ssComposerInput") ||
        document.querySelector("[data-ss-topsearch-input]");
      if (!target) {
        return;
      }
      target.focus();
      if (target.scrollIntoView) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  /* --------------------------------------------------------- think toggle */

  document.querySelectorAll("[data-ss-think]").forEach(function (button) {
    button.addEventListener("click", function () {
      var enabled = button.getAttribute("aria-pressed") === "true";
      var next = !enabled;
      button.setAttribute("aria-pressed", String(next));
      var form = button.closest("form");
      var input = form ? form.querySelector("[data-ss-think-input]") : null;
      if (input) {
        input.value = next ? "1" : "0";
      }
      showToast(
        next
          ? "Think mode on — answers will be reasoned step by step."
          : "Think mode off."
      );
    });
  });

  /* -------------------------------------------------------- chat thread */

  var chatForm = document.getElementById("ssChatForm");

  if (chatForm) {
    var chatInput = document.getElementById("ssComposerInput");
    var thread = document.getElementById("ssThread");
    var chatScroll = document.getElementById("ssChatScroll");
    var typing = document.getElementById("ssTyping");
    var titleEl = document.getElementById("ssChatTitle");
    var sendBtn = chatForm.querySelector(".ss-send");
    var providerLabels = {
      gemini: "Gemini",
      openai: "OpenAI",
      openrouter: "OpenRouter",
      local: "offline",
    };

    var scrollToBottom = function () {
      if (chatScroll) {
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
    };

    window.addEventListener("resize", function () {
      if (chatScroll) {
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
    });

    var autoGrow = function () {
      if (!chatInput) {
        return;
      }
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
    };

    var setChatBusy = function (busy) {
      if (sendBtn) {
        sendBtn.disabled = busy;
        sendBtn.classList.toggle("is-loading", busy);
      }
      if (chatInput) {
        chatInput.disabled = busy;
      }
      if (typing) {
        typing.hidden = !busy;
      }
      if (busy) {
        scrollToBottom();
      }
    };

    var buildMessage = function (role, content, provider) {
      var article = document.createElement("article");
      article.className = "ss-msg ss-msg--" + role;

      if (role === "assistant") {
        var mark = document.createElement("div");
        mark.className = "ss-msg-mark";
        mark.setAttribute("aria-hidden", "true");
        mark.innerHTML =
          '<svg class="ss-icon"><use href="#icon-sparkles"></use></svg>';
        article.appendChild(mark);
      }

      var main = document.createElement("div");
      main.className = "ss-msg-main";

      if (role === "assistant") {
        var meta = document.createElement("div");
        meta.className = "ss-msg-meta";
        meta.textContent = "StudyShare AI";
        if (provider) {
          var badge = document.createElement("span");
          badge.className = "ss-msg-badge ss-msg-badge--" + provider;
          badge.textContent = providerLabels[provider] || provider;
          meta.appendChild(document.createTextNode(" "));
          meta.appendChild(badge);
        }
        main.appendChild(meta);
      }

      var body = document.createElement("div");
      body.className = "ss-md is-rendered";
      body.setAttribute("data-markdown", "");
      body.innerHTML = renderMarkdown(content);
      main.appendChild(body);

      if (role === "assistant") {
        var actions = document.createElement("div");
        actions.className = "ss-msg-actions";
        var copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "ss-msg-action";
        copyButton.setAttribute("data-ss-copy", "");
        copyButton.title = "Copy answer";
        copyButton.innerHTML =
          '<svg class="ss-icon"><use href="#icon-copy"></use></svg>Copy';
        actions.appendChild(copyButton);
        main.appendChild(actions);
      }

      article.appendChild(main);

      if (role === "user") {
        var avatar = document.createElement("span");
        avatar.className = "ss-avatar ss-avatar--sm";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = thread.getAttribute("data-initials") || "";
        article.appendChild(avatar);
      }

      return article;
    };

    if (chatInput) {
      chatInput.addEventListener("input", autoGrow);
      autoGrow();
    }
    scrollToBottom();

    chatForm.addEventListener("submit", function (event) {
      if (!chatInput) {
        return;
      }
      var content = chatInput.value.trim();
      if (!content) {
        event.preventDefault();
        chatInput.focus();
        return;
      }
      if (!window.fetch || !window.FormData) {
        return;
      }

      event.preventDefault();
      var formData = new FormData(chatForm);
      thread.insertBefore(
        buildMessage("user", content, ""),
        typing || null
      );
      chatInput.value = "";
      autoGrow();
      setChatBusy(true);

      fetch(chatForm.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        body: formData,
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { response: response, data: data };
          });
        })
        .then(function (result) {
          if (!result.response.ok || !result.data.ok) {
            throw new Error(
              result.data.error || "The assistant could not answer."
            );
          }
          setChatBusy(false);
          thread.insertBefore(
            buildMessage(
              "assistant",
              result.data.reply.content,
              result.data.reply.provider
            ),
            typing || null
          );
          if (titleEl && result.data.title) {
            titleEl.textContent = result.data.title;
          }
          var metaEl = document.getElementById("ssChatMeta");
          if (metaEl) {
            var messageCount = thread.querySelectorAll(
              ".ss-msg:not(.ss-msg--typing)"
            ).length;
            var replyProvider = result.data.reply.provider;
            var providerName =
              replyProvider && replyProvider !== "local"
                ? providerLabels[replyProvider] || replyProvider
                : "";
            metaEl.textContent =
              "StudyShare AI" +
              (providerName ? " · " + providerName : "") +
              " · " +
              messageCount +
              (messageCount === 1 ? " message" : " messages");
          }
          scrollToBottom();
          chatInput.focus();
        })
        .catch(function (error) {
          setChatBusy(false);
          chatInput.value = content;
          autoGrow();
          showToast(error.message || "The assistant could not answer.");
          scrollToBottom();
        });
    });

    if (chatInput) {
      chatInput.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
          return;
        }
        event.preventDefault();
        if (typeof chatForm.requestSubmit === "function") {
          chatForm.requestSubmit();
        } else {
          chatForm.dispatchEvent(
            new Event("submit", { bubbles: true, cancelable: true })
          );
        }
      });
    }
  }

  /* --------------------------------------------------------------- voice */

  var SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognition = null;
  var activeMic = null;

  document.querySelectorAll("[data-ss-mic]").forEach(function (micButton) {
    micButton.addEventListener("click", function () {
      if (!SpeechRecognition) {
        showToast("Voice input is not supported in this browser.");
        return;
      }

      if (recognition) {
        recognition.stop();
        return;
      }

      var form = micButton.closest("form");
      var target = form
        ? form.querySelector("textarea[name='content'], input[name='content']")
        : promptInput;
      if (!target) {
        return;
      }

      recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = function () {
        activeMic = micButton;
        micButton.classList.add("is-listening");
        showToast("Listening…");
      };

      recognition.onresult = function (event) {
        var transcript = event.results[0][0].transcript;
        target.value = transcript;
        target.focus();
        if (form && form.id === "ssChatForm") {
          target.dispatchEvent(new Event("input", { bubbles: true }));
        }
      };

      recognition.onerror = function () {
        showToast("Could not capture audio. Please try again.");
      };

      recognition.onend = function () {
        if (activeMic) {
          activeMic.classList.remove("is-listening");
        }
        activeMic = null;
        recognition = null;
      };

      try {
        recognition.start();
      } catch (error) {
        micButton.classList.remove("is-listening");
        activeMic = null;
        recognition = null;
        showToast("Voice input could not start.");
      }
    });
  });

  /* -------------------------------------------------------------- escape */

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    setMobileOpen(false);
    setProfileMenu(false);
  });
})();
