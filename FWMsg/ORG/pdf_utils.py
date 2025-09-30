import io
from datetime import datetime
from django.http import HttpResponse
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.conf import settings
import os


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))


class LogoWithBackground(Flowable):
    """Custom flowable for logo with colored background and rounded corners"""
    
    def __init__(self, logo_path, width, height, bg_color, corner_radius=10):
        Flowable.__init__(self)
        self.logo_path = logo_path
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.corner_radius = corner_radius
        self._availWidth = None
        
    def wrap(self, availWidth, availHeight):
        self._availWidth = availWidth  # Store available width for centering
        return self.width, self.height
        
    def draw(self):
        # Get the canvas
        c = self.canv
        
        # Center the logo container within available width
        if self._availWidth:
            x = (self._availWidth - self.width) / 2
        else:
            # Fallback if availWidth is not available
            x = 0
        y = 0
        
        # Draw rounded rectangle background with subtle border
        c.setFillColor(colors.Color(*self.bg_color))
        c.setStrokeColor(colors.Color(*self.bg_color, alpha=0.8))
        c.setLineWidth(1)
        c.roundRect(x, y, self.width, self.height, self.corner_radius, fill=1, stroke=1)
        
        # Add some padding for the logo
        padding = 5
        logo_width = self.width - (2 * padding)
        logo_height = self.height - (2 * padding)
        logo_x = x + padding
        logo_y = y + padding
        
        # Draw the logo
        try:
            img = ImageReader(self.logo_path)
            # Get original image dimensions
            img_width, img_height = img.getSize()
            
            # Calculate scaling to fit within the padded area while maintaining aspect ratio
            scale_x = logo_width / img_width
            scale_y = logo_height / img_height
            scale = min(scale_x, scale_y)
            
            # Calculate final logo dimensions
            final_width = img_width * scale
            final_height = img_height * scale
            
            # Center the logo within the padded area
            final_x = logo_x + (logo_width - final_width) / 2
            final_y = logo_y + (logo_height - final_height) / 2
            
            c.drawImage(self.logo_path, final_x, final_y, final_width, final_height, mask='auto')
        except Exception:
            # If logo fails to load, just show the background
            pass


def generate_application_pdf(bewerber, answers, title_text):
    """Generate a PDF for application answers"""
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Get organization details
    org = bewerber.org
    org_color = hex_to_rgb(org.farbe) if org and org.farbe else (0, 0.48, 1)  # Default blue
    text_color = hex_to_rgb(org.text_color_on_org_color) if org and org.text_color_on_org_color else (0, 0, 0)
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles with organization colors - consistent with survey PDF
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        spaceBefore=10,
        textColor=colors.Color(*org_color),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        spaceBefore=25,
        textColor=colors.Color(*org_color),
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        spaceBefore=15,
        textColor=colors.Color(*org_color),
        fontName='Helvetica-Bold',
        leftIndent=0
    )
    
    answer_style = ParagraphStyle(
        'AnswerStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=15,
        leftIndent=15,
        textColor=colors.black,
        fontName='Helvetica'
    )
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_RIGHT,
        fontName='Helvetica'
    )
    
    # New elegant info label style
    info_label_style = ParagraphStyle(
        'InfoLabelStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.Color(*org_color),
        fontName='Helvetica-Bold'
    )
    
    # Build the PDF content
    story = []
    
    # Add organization logo or header if available
    if org:
        if org.logo:
            try:
                logo_path = os.path.join(settings.MEDIA_ROOT, str(org.logo))
                if os.path.exists(logo_path):
                    # Create smaller, more elegant logo with colored background
                    logo_with_bg = LogoWithBackground(
                        logo_path=logo_path,
                        width=1.8*inch,
                        height=0.9*inch,
                        bg_color=org_color,
                        corner_radius=12
                    )
                    story.append(logo_with_bg)
                    story.append(Spacer(1, 15))
                else:
                    # If logo file doesn't exist, show organization name in styled header
                    org_header_style = ParagraphStyle(
                        'OrgHeader',
                        parent=styles['Normal'],
                        fontSize=12,
                        textColor=colors.Color(*org_color),
                        alignment=TA_CENTER,
                        fontName='Helvetica-Bold',
                        spaceAfter=15
                    )
                    story.append(Paragraph(org.name, org_header_style))
            except Exception:
                # If there's any issue with logo, show organization name
                org_header_style = ParagraphStyle(
                    'OrgHeader',
                    parent=styles['Normal'],
                    fontSize=12,
                    textColor=colors.Color(*org_color),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold',
                    spaceAfter=15
                )
                story.append(Paragraph(org.name, org_header_style))
        else:
            # No logo configured, show organization name in styled header
            org_header_style = ParagraphStyle(
                'OrgHeader',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.Color(*org_color),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=15
            )
            story.append(Paragraph(org.name, org_header_style))
    
    # Title
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 25))
    
    # Application information in a more elegant format
    application_info = []
    if org:
        application_info.append([Paragraph(_("Organisation:"), info_label_style), org.name])
    
    application_info.extend([
        [Paragraph(_("Name:"), info_label_style), f"{bewerber.user.first_name} {bewerber.user.last_name}"],
        [Paragraph(_("E-Mail:"), info_label_style), bewerber.user.email],
        [Paragraph(_("Erstellt am:"), info_label_style), datetime.now().strftime("%d.%m.%Y um %H:%M")],
    ])
    
    info_table = Table(application_info, colWidths=[1.2*inch, 4.3*inch])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 12),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.Color(*org_color, alpha=0.3)),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 25))
    
    # Questions and answers section
    story.append(Paragraph(_("Antworten"), heading_style))
    story.append(Spacer(1, 15))
    
    if not answers:
        story.append(Paragraph(_("Keine Antworten aufgezeichnet."), answer_style))
    else:
        for i, answer in enumerate(answers, 1):
            # Create a more elegant question layout
            question_text = f"<b>{answer.question.order}.</b> {answer.question.question}"
            if hasattr(answer.question, 'description') and answer.question.description:
                question_text += f"<br/><i>{answer.question.description}</i>"
            
            story.append(Paragraph(question_text, question_style))
            
            # Answer content with better formatting
            if answer.answer:
                answer_content = answer.answer
                story.append(Paragraph(answer_content, answer_style))
            else:
                story.append(Paragraph("<i>Keine Antwort</i>", answer_style))
            
            # Add subtle separator between questions (except for the last one)
            if i < len(answers):
                story.append(Spacer(1, 8))
                story.append(HRFlowable(width="50%", thickness=0.5, color=colors.Color(*org_color, alpha=0.2), hAlign='LEFT'))
                story.append(Spacer(1, 8))
    
    # Footer
    story.append(Spacer(1, 25))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.Color(*org_color, alpha=0.3)))
    story.append(Spacer(1, 8))
    
    footer_text = _("Erstellt am {date}").format(
        date=datetime.now().strftime("%d.%m.%Y um %H:%M")
    )
    if org:
        footer_text += f" • {org.name}"
    
    story.append(Paragraph(footer_text, info_style))
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and return it
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf


def create_pdf_response(pdf_content, filename):
    """Create HTTP response for PDF download"""
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def generate_full_application_pdf(bewerber):
    """Generate PDF for complete application"""
    from BW.models import ApplicationAnswer
    
    answers = ApplicationAnswer.objects.filter(user=bewerber.user).order_by('question__order')
    title_text = f"Bewerbung von {bewerber.user.first_name} {bewerber.user.last_name}"
    
    return generate_application_pdf(bewerber, answers, title_text)


def generate_selected_application_pdf(bewerber, selected_question_ids):
    """Generate PDF for selected application questions"""
    from BW.models import ApplicationAnswer
    
    answers = ApplicationAnswer.objects.filter(
        user=bewerber.user,
        question_id__in=selected_question_ids
    ).order_by('question__order')
    
    title_text = f"Ausgewählte Antworten von {bewerber.user.first_name} {bewerber.user.last_name}"
    
    return generate_application_pdf(bewerber, answers, title_text)
