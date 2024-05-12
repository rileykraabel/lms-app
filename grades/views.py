from django.contrib.auth import authenticate, login, logout
from django.http import Http404
from django.http import HttpResponseBadRequest
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
from . import models

def is_student(user):
    return user.groups.filter(name="Students").exists()

def is_ta(user):
    return user.groups.filter(name="Teaching Assistants").exists()

def is_admin(user):
    return user.username == "pavpan" and user.is_superuser

def is_ta_or_admin(user):
    return is_ta(user) or is_admin(user)

def determine_user_type(user):
    if user.is_authenticated:
        if is_student(user):
            return "Student"
        elif is_ta(user):
            return "TA"
        elif is_admin(user):
            return "Admin"
        else:
            return "Other"
    else:
        return "AnonymousUser"

def calculate_final_grade(user):
    if is_student(user):
        submissions = models.Submission.objects.filter(author=user)
        weighted_sum = 0
        total_weights = 0

        for submission in submissions:
            if submission.score is not None and submission.assignment.weight is not None:
                weighted_sum += submission.score * submission.assignment.weight
                total_weights += submission.assignment.weight

        weighted_avg = weighted_sum / total_weights
        return round(weighted_avg, 1)

def pick_grader(assignment):
    return (
        models.User.objects
            .filter(groups__name='Teaching Assistants')  # Select the "Teaching Assistants" group
            .annotate(total_assigned=Count('graded_set', distinct=True, filter=Q(graded_set__assignment=assignment)))
            .order_by('total_assigned')
            .first()
    )

def view(request):
    user = request.user
    user_type = determine_user_type(user)
    return render(request, 'my_template.html', {'user_type': user_type})

@login_required
def assignments(request):
    try:
        all_assignments = models.Assignment.objects.all()
        return render(request, "assignments.html", {'assignments': all_assignments})
    except Http404:
        raise Http404

@login_required
def index(request, assignment_id):
    try:
        description = models.Assignment.description
        id = models.Assignment.objects.get(pk=assignment_id)
        user_type = determine_user_type(request.user)

        if user_type in ["TA", "Admin"]:
            # Information for TA or Admin
            total_submissions = models.Submission.objects.filter(assignment=id).count()
            current_submissions = models.Submission.objects.filter(assignment=id).count()
            ta_assignments = models.Submission.objects.filter(assignment=id, grader_id=request.user).count()
            total_students = models.Group.objects.get(name="Students").user_set.count()

            info = {
                'description': description,
                'assignment': id,
                'current_submissions': current_submissions,
                'ta_assignments': ta_assignments,
                'total_submissions': total_submissions,
                'total_students': total_students,
                'is_staff': True,
                'show_submission_details': False  # Set this to False for TA and Admin views
            }

        else:
            # Information for Students
            submission = models.Submission.objects.filter(assignment=id, author=request.user).first()
            info = {
                'description': description,
                'assignment': id,
                'submission': submission,
                'is_staff': False,
                'show_submission_details': True  # Set this to True for Student view
            }

        return render(request, "index.html", info)

    except Http404:
        raise Http404

@login_required
def show_upload(request, filename):
    try:
        submission = models.Submission.objects.get(file=filename)
        if not (
                request.user == submission.author or
                request.user == submission.grader or
                request.user.is_staff
        ):
            raise PermissionDenied
        else:
            with submission.file.open() as fd:
                response = HttpResponse(fd.read(), content_type='application/pdf')  # Adjust the content type as needed
                response["Content-Disposition"] = f'attachment; filename="{submission.file.name}"'
                return response
    except Http404:
        raise Http404

@login_required
@user_passes_test(is_student)
def submit_assignment(request, assignment_id):
    try:
        assignment = models.Assignment.objects.get(id=assignment_id)
        print("assignment due date:", assignment.deadline)
        print("assignment past due:", assignment.deadline < timezone.now())

        if request.method == 'POST':
            if assignment.is_due():
                print("due")
                return HttpResponseBadRequest("Assignment is past due and can no longer be submitted.")

            submitted_file = request.FILES.get('file')

            if models.Submission.objects.filter(assignment=assignment, author=request.user).exists():
                submission = models.Submission.objects.filter(assignment=assignment_id, author=request.user)
                submission.file = submitted_file
            else:
                new_submission = models.Submission.objects.create(assignment=assignment, author=request.user, grader=pick_grader(assignment), file=submitted_file, score=None)
                new_submission.save()

            return redirect('assignment_id', assignment_id=assignment.id)

        return render(request, 'index.html', {'assignment': assignment})

    except Http404:
        raise Http404

@user_passes_test(is_ta_or_admin)
def submissions(request, assignment_id):
    try:
        id = models.Assignment.objects.get(pk=assignment_id)
        user_type = determine_user_type(request.user)

        if user_type == "TA":
            submissions = models.Submission.objects.filter(assignment=id, grader_id=request.user).all().order_by('author__username')
            info = {
                'assignment': id,
                'submissions': submissions,
                'user_type': user_type
            }

        elif user_type == "Admin":
            submissions = models.Submission.objects.filter(assignment=id).all().order_by('author__username')
            info = {
                'assignment': id,
                'submissions': submissions,
                'user_type': user_type
            }

        return render(request, "submissions.html", info)
    except Http404:
        raise Http404

@user_passes_test(is_ta)
def grade(request, assignment_id):
    try:
        if request.method == "POST":
            for key, value in request.POST.items():
                if key.startswith('grade-'):
                    try:
                        submission_id = int(key.split('-')[1])
                        submission = models.Submission.objects.get(pk=submission_id)
                        submission.score = float(value) if value.strip() else None
                        submission.save()
                    except (ValueError, models.Submission.DoesNotExist):
                        pass

        return redirect('submissions', assignment_id=assignment_id)
    except Http404:
        raise Http404

@login_required
def profile(request):
    try:
        current_user = request.user
        user_type = determine_user_type(current_user)
        current_time = timezone.now()
        assignments = models.Assignment.objects.all()
        assignment_info_list = []

        if user_type == "Student":
            final_grade = calculate_final_grade(current_user)
            for assignment in assignments:
                submission = models.Submission.objects.filter(assignment=assignment, author=current_user).first()
                if assignment.deadline < current_time:
                    if submission and submission.score is not None:
                        status = f"{submission.score}%"
                    elif submission is not None and submission.score is None:
                        status = "Ungraded"
                    else:
                        status = "Missing"
                else:
                    status = "Not Due"

                assignment_info = {
                    'assignment': assignment,
                    'status': status,
                    'final_grade': final_grade,
                    'user_type': "Student"
                }
                assignment_info_list.append(assignment_info)

        elif user_type == "TA":
            for assignment in assignments:
                ta_assignments = models.Submission.objects.filter(assignment=assignment, grader_id=current_user).count()
                graded_assignments = models.Submission.objects.filter(assignment=assignment, grader_id=current_user, score__isnull=False).count()
                if assignment.deadline < current_time:
                    assignment.to_grade = f"{graded_assignments} / {ta_assignments}"
                    assignment.save()
                else:
                    assignment.to_grade = "Not due"
                    assignment.save()

                assignment_info = {
                    'assignment': assignment,
                    'assignments': assignments,
                    'ta_assignments': ta_assignments,
                    'graded': graded_assignments,
                    'status': assignment.to_grade,
                }
                assignment_info_list.append(assignment_info)

        elif user_type == "Admin":
            for assignment in assignments:
                graded_assignments = models.Submission.objects.filter(assignment=assignment, score__isnull=False).count()
                if assignment.deadline < current_time:
                    assignment.to_grade = f"{graded_assignments} / {models.Submission.objects.filter(assignment=assignment).count()}"
                    assignment.save()
                else:
                    assignment.to_grade = "Not due"
                    assignment.save()

                assignment_info = {
                    'assignment': assignment,
                    'assignments': assignments,
                    'number_of_assignments': models.Submission.objects.filter(assignment=assignment).count(),
                    'graded': graded_assignments,
                    'status': assignment.to_grade,
                    'is_admin': True
                }
                assignment_info_list.append(assignment_info)

        return render(request, "profile.html", {'assignment_info_list': assignment_info_list})
    except Http404:
        raise Http404

def login_form(request):
    try:
        next_page = request.GET.get('next', '/profile') or '/profile'
        print('current next:', next_page)

        if request.method == 'POST':
            username = request.POST.get('username', "")
            password = request.POST.get('password', "")

            if username and password:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    return redirect(next_page)
                else:
                    return render(request, 'login.html', {'error_message': 'Username and password do not match'})

        return render(request, "login.html", {'next_page': next_page})
    except Http404:
        raise Http404

def logout_form(request):
    try:
        logout(request)
        return redirect('/profile/login')
    except Http404:
        raise Http404