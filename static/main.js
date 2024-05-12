import { $ } from "/static/jquery/src/jquery.js";
export function say_hi(elt) {
  console.log("Say hi to", elt);
}

say_hi($("h1"));

export function make_table_sortable(tableElement) {
  // Select the last header cell in the table header
  const sortableHeaders = tableElement.find("thead th.sortable");

  sortableHeaders.on("click", function() {
      // Determine the current state of the table
      const currentHeader = $(this);
      const isAscending = currentHeader.hasClass("sort-asc");
      const isDescending = currentHeader.hasClass("sort-desc");
      const isUnsorted = !isAscending && !isDescending;
      
      // Toggle sorting order
      if (isUnsorted) {
        currentHeader.addClass("sort-asc");
      } else if (isAscending) {
        currentHeader.removeClass("sort-asc").addClass("sort-desc");
      } else {
        currentHeader.removeClass("sort-desc");
      }        
      
      sortableHeaders.not(currentHeader).removeClass("sort-asc sort-desc");
      const columnIndex = currentHeader.index();

      // Select all rows inside tbody
      const tbodyRowsArray = tableElement.find('tbody tr').toArray();

      // Sort the array based on the numeric value of the last td
      tbodyRowsArray.sort(function(a, b) {
        const aValue = isUnsorted ? parseInt($(a).data("index")) : parseFloat($(a).find(`td:eq(${columnIndex})`).data("value"));
        const bValue = isUnsorted ? parseInt($(b).data("index")) : parseFloat($(b).find(`td:eq(${columnIndex})`).data("value"));

        return isDescending ? bValue - aValue : aValue - bValue;
      });

      // Wrap the sorted array back into a jQuery object and append to tbody
      $(tbodyRowsArray).appendTo(tableElement.find('tbody'));
  });
}

export function make_form_async($form) {
  if ($form.length === 0) {
    console.error("Form element not found.");
    return;
  }

  $form.on('submit', function (event) {
    event.preventDefault();

    $form.find('input[type="file"]').prop('disabled', true);
    $form.find('button[type="submit"]').prop('disabled', true);
    let formData = new FormData($form[0]);

    $.ajax({
      url: $form.attr("action"),
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      mimeType: $form.attr("enctype"),
      headers: {
        "X-CSRFToken": $form.find('input[name="csrfmiddlewaretoken"]').val()
      },

      success: function (data) {
        console.log('Form submitted successfully:', data);
        $form.replaceWith('<p>Upload succeeded</p>');
      },

      error: function (error) {
        console.error('Error submitting form:', error);
        $form.find('input[type="file"]').prop('disabled', false);
        $form.find('button[type="submit"]').prop('disabled', false);
      }
    });
  });
}

export function make_grade_hypothesized($tableElement) {
  const $button = $("<button>").text("Hypothesize Grades").insertBefore($tableElement);

  let originalData = null; // Variable to store original data

  $button.on("click", function () {
      const hypothesized = $tableElement.hasClass("hypothesized");

      if (hypothesized) {
          // Restoring original data
          if (originalData) {
              originalData.forEach(({ $cell, originalText }) => {
                  $cell.empty().text(originalText);
              });
          }
          originalData = null; // Clear stored data
      } else {
          // Storing original data
          originalData = [];
          $tableElement.find("td.numbers").each(function () {
              const $cell = $(this);
              const originalText = $cell.text();
              originalData.push({ $cell, originalText });
          });

          // Switching to hypothesized state
          $tableElement.find("td.numbers[data-value='Not Due'], td.numbers[data-value='Ungraded']").each(function () {
              const $cell = $(this);
              const originalText = $cell.text();
              $cell.empty().append($("<input>").attr("type", "number").data("original-text", originalText));
          });
      }

      $tableElement.toggleClass("hypothesized");
      compute_final_grade($tableElement);
  });

  // Event handler for input changes
  $tableElement.on("change", "td.numbers input", function () {
      // Recalculate final grade on input change
      compute_final_grade($tableElement);
  });

  // Initial grade computation
  compute_final_grade($tableElement);
}

export function compute_final_grade($tableElement) {
  const hypothesized = $tableElement.hasClass("hypothesized");
  let totalPoints = 0;
  let totalWeight = 0;

  $tableElement.find("tbody tr").each(function () {
      const $row = $(this);
      const $statusCell = $row.find("td.numbers");
      const weight = parseFloat($statusCell.data("weight"));

      if (!hypothesized && ($statusCell.text() === "Not Due" || $statusCell.text() === "Ungraded")) {
          return;
      }

      let inputValue;

      if (hypothesized) {
        inputValue = parseFloat($statusCell.find("input").val());
      } else {
        inputValue = $statusCell.data("original-text");
        inputValue = (inputValue === "Missing" || inputValue === "Not Due" || inputValue === "Ungraded") ? 0 : parseFloat(inputValue);
      }

      // Ensure inputValue is a valid number
      if (!isNaN(inputValue)) {
        if (inputValue === 0 && $statusCell.data("original-text") === "Missing") {
          totalWeight += weight;
        } else {
          totalPoints += (inputValue / 100) * weight;
          totalWeight += weight;
        }
      }
  });

  const finalGrade = totalWeight === 0 ? 0 : (totalPoints / totalWeight) * 100;

  // Display the final grade only if in hypothesized state
  if (hypothesized) {
      $tableElement.find("tfoot td.numbers").text(finalGrade.toFixed(2) + "%");
  }
}