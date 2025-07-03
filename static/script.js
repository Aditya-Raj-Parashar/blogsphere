// Custom JavaScript for BlogSphere

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Form validation
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // File upload preview
    var fileInput = document.getElementById('files');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            var files = e.target.files;
            var preview = document.getElementById('file-preview');
            
            if (!preview) {
                preview = document.createElement('div');
                preview.id = 'file-preview';
                preview.className = 'mt-3';
                fileInput.parentNode.insertBefore(preview, fileInput.nextSibling);
            }
            
            preview.innerHTML = '';
            
            for (var i = 0; i < files.length; i++) {
                var file = files[i];
                var filePreview = document.createElement('div');
                filePreview.className = 'file-preview-item mb-2 p-2 border rounded';
                
                var fileName = document.createElement('span');
                fileName.textContent = file.name;
                fileName.className = 'me-2';
                
                var fileSize = document.createElement('small');
                fileSize.textContent = '(' + (file.size / 1024 / 1024).toFixed(2) + ' MB)';
                fileSize.className = 'text-muted';
                
                filePreview.appendChild(fileName);
                filePreview.appendChild(fileSize);
                
                if (file.type.startsWith('image/')) {
                    var img = document.createElement('img');
                    img.src = URL.createObjectURL(file);
                    img.className = 'img-thumbnail mt-2';
                    img.style.maxWidth = '200px';
                    img.style.maxHeight = '200px';
                    filePreview.appendChild(img);
                }
                
                preview.appendChild(filePreview);
            }
        });
    }

    // Confirm delete actions
    var deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        });
    });

    // Add loading state to forms
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            var submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Please wait...';
            }
        });
    });

    // Character counter for textareas
    var textareas = document.querySelectorAll('textarea');
    textareas.forEach(function(textarea) {
        var maxLength = textarea.getAttribute('maxlength');
        if (maxLength) {
            var counter = document.createElement('div');
            counter.className = 'form-text text-end';
            counter.textContent = '0 / ' + maxLength;
            textarea.parentNode.appendChild(counter);
            
            textarea.addEventListener('input', function() {
                counter.textContent = textarea.value.length + ' / ' + maxLength;
                if (textarea.value.length > maxLength * 0.9) {
                    counter.className = 'form-text text-end text-warning';
                } else if (textarea.value.length === parseInt(maxLength)) {
                    counter.className = 'form-text text-end text-danger';
                } else {
                    counter.className = 'form-text text-end';
                }
            });
        }
    });

    // Add animation to cards on scroll
    var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in');
            }
        });
    });

    document.querySelectorAll('.card').forEach(function(card) {
        observer.observe(card);
    });

    // Search functionality (if search input exists)
    var searchInput = document.getElementById('search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            var searchTerm = this.value.toLowerCase();
            var posts = document.querySelectorAll('.post-card');
            
            posts.forEach(function(post) {
                var title = post.querySelector('.card-title').textContent.toLowerCase();
                var content = post.querySelector('.card-text').textContent.toLowerCase();
                
                if (title.includes(searchTerm) || content.includes(searchTerm)) {
                    post.style.display = 'block';
                } else {
                    post.style.display = 'none';
                }
            });
        });
    }

    // Back to top button
    var backToTopBtn = document.createElement('button');
    backToTopBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
    backToTopBtn.className = 'btn btn-primary btn-floating';
    backToTopBtn.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 1000; border-radius: 50%; width: 50px; height: 50px; display: none;';
    document.body.appendChild(backToTopBtn);

    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopBtn.style.display = 'block';
        } else {
            backToTopBtn.style.display = 'none';
        }
    });

    backToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
});

// Utility functions
function showToast(message, type = 'info') {
    var toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    
    setTimeout(function() {
        toast.remove();
    }, 5000);
}

function formatDate(dateString) {
    var date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function validateEmail(email) {
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePassword(password) {
    return password.length >= 8;
}

// Image lazy loading
function lazyLoadImages() {
    var images = document.querySelectorAll('img[data-src]');
    var imageObserver = new IntersectionObserver(function(entries, observer) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                var image = entry.target;
                image.src = image.dataset.src;
                image.classList.remove('lazy');
                imageObserver.unobserve(image);
            }
        });
    });

    images.forEach(function(image) {
        imageObserver.observe(image);
    });
}

// Initialize lazy loading
lazyLoadImages();
