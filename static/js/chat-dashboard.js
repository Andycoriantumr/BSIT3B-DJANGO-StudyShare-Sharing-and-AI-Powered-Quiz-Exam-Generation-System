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

  document.querySelectorAll("[data-share-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (form.dataset.hasShare !== "true" && !window.confirm(
        "Anyone with the public link can view this conversation. Uploaded files and private quiz answer keys will not be shared. Continue?"
      )) {
        return;
      }

      var button = form.querySelector("button[type='submit']");
      if (button) {
        button.disabled = true;
      }
      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" }
      }).then(function (response) {
        if (!response.ok) {
          throw new Error("The public link could not be created.");
        }
        return response.json();
      }).then(function (result) {
        if (!result.ok || !result.share_url) {
          throw new Error("The server did not return a share link.");
        }
        form.dataset.hasShare = "true";
        if (button) {
          button.textContent = "Copy public link";
        }
        var revokeForm = form.parentElement.querySelector("[data-revoke-form]");
        if (revokeForm) {
          revokeForm.hidden = false;
        }
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
          window.prompt("Copy this public link:", result.share_url);
          showToast("Public link created.");
          return;
        }
        return navigator.clipboard.writeText(result.share_url).then(function () {
          showToast("Public link copied.");
        }).catch(function () {
          window.prompt("Copy this public link:", result.share_url);
          showToast("Public link created; copy it from the dialog.");
        });
      }).catch(function (error) {
        showToast(error.message || "Unable to create the public link.");
      }).finally(function () {
        if (button) {
          button.disabled = false;
        }
      });
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });

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

  function initAttachmentControls() {
    document.querySelectorAll("[data-ss-attachment-control]").forEach(function (control) {
      var form = control.closest("form");
      var preview = form ? form.querySelector("[data-ss-attachment-preview]") : null;
      if (!preview) {
        return;
      }
      var maxFiles = parseInt(control.getAttribute("data-ss-max-files") || "5", 10);
      if (isNaN(maxFiles) || maxFiles < 1) {
        maxFiles = 5;
      }
      var previousSelections = new WeakMap();

      function selectedFiles() {
        var files = [];
        control.querySelectorAll("[data-ss-file-input]").forEach(function (input) {
          Array.prototype.forEach.call(input.files || [], function (file) {
            files.push({
              input: input,
              file: file,
            });
          });
        });
        return files;
      }

      function countFilesInOtherInputs(input) {
        var count = 0;
        control.querySelectorAll("[data-ss-file-input]").forEach(function (other) {
          if (other !== input) {
            count += (other.files || []).length;
          }
        });
        return count;
      }

      function mergeNewSelection(input) {
        if (!window.DataTransfer || !input.files) {
          return;
        }
        var previous = previousSelections.get(input) || [];
        var picked = Array.prototype.slice.call(input.files);
        var available = Math.max(0, maxFiles - countFilesInOtherInputs(input));
        var combined = [];
        var seen = {};
        previous.concat(picked).forEach(function (file) {
          var key = file.name + ":" + file.size + ":" + file.lastModified;
          if (!seen[key]) {
            seen[key] = true;
            combined.push(file);
          }
        });
        if (combined.length > available) {
          showToast("You can attach up to " + maxFiles + " files at once.");
          combined = combined.slice(0, available);
        }
        var transfer = new DataTransfer();
        combined.forEach(function (file) {
          transfer.items.add(file);
        });
        input.files = transfer.files;
        previousSelections.set(input, combined);
      }

      function renderPreview() {
        var files = selectedFiles();
        preview.replaceChildren();
        preview.hidden = files.length === 0;
        form.classList.toggle("ss-has-attachments", files.length > 0);
        var countControl = form.querySelector("[data-ss-question-count]");
        if (countControl) {
          countControl.hidden = files.length === 0;
        }
        files.forEach(function (attachment, index) {
          var chip = document.createElement("span");
          chip.className = "ss-attachment-chip";
          var label = document.createElement("span");
          label.className = "ss-attachment-chip-label";
          label.textContent = attachment.file.name;
          chip.appendChild(label);

          var remove = document.createElement("button");
          remove.className = "ss-attachment-chip-remove";
          remove.type = "button";
          remove.setAttribute("aria-label", "Remove " + label.textContent);
          remove.textContent = "×";
          remove.addEventListener("click", function () {
            if (window.DataTransfer) {
              var nextFiles = new DataTransfer();
              Array.prototype.forEach.call(attachment.input.files, function (file, fileIndex) {
                if (fileIndex !== indexForInput(files, index, attachment.input)) {
                  nextFiles.items.add(file);
                }
              });
              attachment.input.files = nextFiles.files;
            } else {
              attachment.input.value = "";
            }
            previousSelections.set(
              attachment.input,
              Array.prototype.slice.call(attachment.input.files || [])
            );
            renderPreview();
          });
          chip.appendChild(remove);
          preview.appendChild(chip);
        });
      }

      function indexForInput(files, currentIndex, input) {
        var index = -1;
        for (var i = 0; i <= currentIndex; i += 1) {
          if (files[i].input === input) {
            index += 1;
          }
        }
        return index;
      }

      control.querySelectorAll("[data-ss-file-input]").forEach(function (input) {
        input.addEventListener("click", function () {
          previousSelections.set(
            input,
            Array.prototype.slice.call(input.files || [])
          );
        });
        input.addEventListener("change", function () {
          mergeNewSelection(input);
          renderPreview();
        });
      });
      control.querySelectorAll("label[for]").forEach(function (label) {
        label.addEventListener("keydown", function (event) {
          if (event.key !== "Enter" && event.key !== " ") {
            return;
          }
          var input = document.getElementById(label.getAttribute("for"));
          if (input) {
            event.preventDefault();
            input.click();
          }
        });
      });
      form.addEventListener("reset", function () {
        window.setTimeout(renderPreview, 0);
      });
      renderPreview();
    });
  }

  initAttachmentControls();

  /* -------------------------------------------------------- generated quiz */

  function initQuizzes() {
    document.querySelectorAll("[data-ss-quiz]").forEach(function (quiz) {
      var form = quiz.querySelector("[data-ss-quiz-form]");
      var scoreEl = quiz.querySelector("[data-ss-quiz-score]");
      var submitBtn = quiz.querySelector(".ss-quiz-submit");
      var retryBtn = quiz.querySelector("[data-ss-quiz-retry]");
      if (!form || !scoreEl || !submitBtn) {
        return;
      }

      function csrfToken() {
        var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : "";
      }

      function answerInputs() {
        return form.querySelectorAll("[data-ss-quiz-answer]");
      }

      function collectAnswers() {
        var answers = {};
        quiz.querySelectorAll("[data-ss-quiz-question]").forEach(function (question) {
          var index = question.getAttribute("data-index");
          var selected = question.querySelector('input[type="radio"]:checked');
          if (selected) {
            answers[index] = selected.value;
            return;
          }
          var text = question.querySelector("[data-ss-quiz-answer]");
          answers[index] = text ? text.value : "";
        });
        return answers;
      }

      function firstUnanswered() {
        var missing = null;
        quiz.querySelectorAll("[data-ss-quiz-question]").forEach(function (question) {
          if (missing) {
            return;
          }
          var radios = question.querySelectorAll('input[type="radio"]');
          if (radios.length && !question.querySelector('input[type="radio"]:checked')) {
            missing = question;
          }
        });
        return missing;
      }

      function setBusy(busy) {
        submitBtn.disabled = busy;
        submitBtn.textContent = busy ? "Checking…" : "Submit answers";
      }

      function renderFeedback(question, item) {
        question.classList.remove("is-correct", "is-incorrect", "is-review");
        var feedback = question.querySelector("[data-ss-quiz-feedback]");
        if (!feedback) {
          return;
        }
        feedback.replaceChildren();
        feedback.hidden = false;

        var status = document.createElement("p");
        status.className = "ss-quiz-feedback-status";
        if (!item.graded) {
          question.classList.add("is-review");
          status.textContent = "Not auto-scored";
        } else if (item.correct) {
          question.classList.add("is-correct");
          status.textContent = "Correct";
        } else {
          question.classList.add("is-incorrect");
          status.textContent = "Incorrect";
        }
        feedback.appendChild(status);

        if (item.answer) {
          var answer = document.createElement("p");
          answer.className = "ss-quiz-feedback-answer";
          if (!item.graded) {
            answer.textContent = "Reference answer: " + item.answer;
          } else if (item.correct) {
            answer.textContent = "Answer: " + item.answer;
          } else {
            answer.textContent = "Correct answer: " + item.answer;
          }
          feedback.appendChild(answer);
        }

        if (item.explanation) {
          var explanation = document.createElement("p");
          explanation.className = "ss-quiz-feedback-explanation";
          explanation.textContent = "Explanation: " + item.explanation;
          feedback.appendChild(explanation);
        }
      }

      function renderScore(data) {
        var percent = Number(data.percent) || 0;
        var tone = !data.total
          ? ""
          : percent >= 80
            ? "is-great"
            : percent >= 50
              ? "is-ok"
              : "is-low";
        scoreEl.hidden = false;
        scoreEl.className = "ss-quiz-score" + (tone ? " " + tone : "");
        scoreEl.replaceChildren();

        var summary = document.createElement("span");
        if (data.total) {
          summary.textContent =
            "You scored " + data.score + " / " + data.total +
            " (" + percent + "%).";
        } else {
          summary.textContent = "Answer key unlocked.";
        }
        scoreEl.appendChild(summary);

        var results = data.results || [];
        var hasReview = results.some(function (item) { return !item.graded; });
        if (hasReview) {
          var note = document.createElement("p");
          note.className = "ss-quiz-score-note";
          note.textContent =
            "Written answers are not auto-scored. Compare them with the answer key below.";
          scoreEl.appendChild(note);
        }

        var progressLink = document.createElement("a");
        progressLink.className = "ss-quiz-progress-link";
        progressLink.href = quiz.getAttribute("data-progress-url");
        progressLink.textContent = "View My Progress";
        scoreEl.appendChild(progressLink);

        results.forEach(function (item) {
          var question = quiz.querySelector(
            '[data-ss-quiz-question][data-index="' + item.index + '"]'
          );
          if (question) {
            renderFeedback(question, item);
          }
        });

        answerInputs().forEach(function (input) {
          input.disabled = true;
        });
        submitBtn.hidden = true;
        if (retryBtn) {
          retryBtn.hidden = false;
        }
        scoreEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }

      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!window.fetch) {
          showToast("This browser cannot submit the quiz.");
          return;
        }
        var missing = firstUnanswered();
        if (missing) {
          showToast("Answer every question before submitting.");
          var first = missing.querySelector('input[type="radio"]');
          if (first) {
            first.focus();
          }
          missing.scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
        setBusy(true);

        fetch(quiz.getAttribute("data-grade-url"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            "X-Requested-With": "XMLHttpRequest",
            Accept: "application/json",
          },
          credentials: "same-origin",
          body: JSON.stringify({ answers: collectAnswers() }),
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { response: response, data: data };
            });
          })
          .then(function (result) {
            if (!result.response.ok || !result.data.ok) {
              throw new Error(result.data.error || "Could not check the quiz.");
            }
            setBusy(false);
            renderScore(result.data);
          })
          .catch(function (error) {
            setBusy(false);
            showToast(error.message || "Could not check the quiz.");
          });
      });

      if (retryBtn) {
        retryBtn.addEventListener("click", function () {
          form.reset();
          answerInputs().forEach(function (input) {
            input.disabled = false;
          });
          quiz.querySelectorAll("[data-ss-quiz-question]").forEach(function (question) {
            question.classList.remove("is-correct", "is-incorrect", "is-review");
            var feedback = question.querySelector("[data-ss-quiz-feedback]");
            if (feedback) {
              feedback.hidden = true;
              feedback.replaceChildren();
            }
          });
          scoreEl.hidden = true;
          scoreEl.className = "ss-quiz-score";
          scoreEl.replaceChildren();
          retryBtn.hidden = true;
          submitBtn.hidden = false;
          setBusy(false);
          var first = form.querySelector("[data-ss-quiz-answer]");
          if (first) {
            first.focus();
          }
        });
      }
    });
  }

  initQuizzes();

  function formHasAttachments(form) {
    if (!form) {
      return false;
    }
    return Array.prototype.some.call(
      form.querySelectorAll("[data-ss-file-input]"),
      function (input) { return input.files && input.files.length > 0; }
    );
  }

  function normalizeQuestionCount(form) {
    var input = form
      ? form.querySelector("[data-ss-question-count-input]")
      : null;
    if (!input) {
      return;
    }
    var count = parseInt(input.value, 10);
    if (isNaN(count)) {
      count = 10;
    }
    count = Math.max(1, Math.min(50, count));
    input.value = String(count);
  }

  function attachmentLabels(form) {
    var labels = [];
    if (!form) {
      return labels;
    }
    form.querySelectorAll("[data-ss-file-input]").forEach(function (input) {
      Array.prototype.forEach.call(input.files || [], function (file) {
        labels.push(file.name);
      });
    });
    return labels;
  }

  function clearAttachments(form) {
    if (!form) {
      return;
    }
    form.querySelectorAll("[data-ss-file-input]").forEach(function (input) {
      input.value = "";
    });
    var preview = form.querySelector("[data-ss-attachment-preview]");
    if (preview) {
      preview.replaceChildren();
      preview.hidden = true;
    }
    var countControl = form.querySelector("[data-ss-question-count]");
    if (countControl) {
      countControl.hidden = true;
    }
  }

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
      if (!promptInput.value.trim() && !formHasAttachments(promptForm)) {
        event.preventDefault();
        promptInput.focus();
        return;
      }
      if (!window.fetch || !window.FormData) {
        return;
      }

      event.preventDefault();
      normalizeQuestionCount(promptForm);
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

    var buildMessage = function (role, content, provider, attachments) {
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

      if (role === "user" && attachments && attachments.length) {
        var attachmentList = document.createElement("div");
        attachmentList.className = "ss-msg-attachments";
        attachments.forEach(function (name) {
          var chip = document.createElement("span");
          chip.className = "ss-msg-attachment";
          chip.textContent = name;
          attachmentList.appendChild(chip);
        });
        main.appendChild(attachmentList);
      }

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
      if (!content && !formHasAttachments(chatForm)) {
        event.preventDefault();
        chatInput.focus();
        return;
      }
      if (!window.fetch || !window.FormData) {
        return;
      }

      event.preventDefault();
      normalizeQuestionCount(chatForm);
      var formData = new FormData(chatForm);
      var attachedLabels = attachmentLabels(chatForm);
      thread.insertBefore(
        buildMessage("user", content, "", attachedLabels),
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
          if (result.data.reply.has_quiz) {
            setChatBusy(false);
            window.location.reload();
            return;
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
          clearAttachments(chatForm);
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
