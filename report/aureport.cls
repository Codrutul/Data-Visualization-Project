%% aureport.cls — Data Visualization course project report (Aarhus University)
%% A LaTeX counterpart of the Typst template in ../typst-au-report: full-bleed photo cover
%% in AU blue with a slanted cut, section name + page number in the header, blue sans-serif
%% headings, booktabs tables, author-year (APA) citations, lettered appendices.
%% Requires XeLaTeX or LuaLaTeX (fontspec). MIT licence.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{aureport}[2026/09/16 v0.1 AU Data Visualization course report]

\LoadClass[10pt,a4paper]{article}

\RequirePackage{iftex}
\ifXeTeX\else\ifLuaTeX\else
  \ClassError{aureport}{Compile with XeLaTeX or LuaLaTeX (set the compiler in Overleaf's menu)}{}
\fi\fi

% ----- Packages ----------------------------------------------------------------
\RequirePackage{fontspec}
\RequirePackage[a4paper, top=2.6cm, left=2.6cm, right=2.2cm, bottom=2cm, headsep=0.55cm]{geometry}
\RequirePackage{xcolor}
\RequirePackage{graphicx}
\RequirePackage{tikz}
\RequirePackage{booktabs}
\RequirePackage{array}
\RequirePackage{tabularx}
\RequirePackage{caption}
\RequirePackage{enumitem}
\RequirePackage{microtype}
\RequirePackage{titlesec}
\RequirePackage{fancyhdr}
\RequirePackage{etoolbox}
\RequirePackage{xparse}
\RequirePackage{calc}

% ----- Colours and fonts --------------------------------------------------------
\definecolor{aublue}{HTML}{003D73}

% Headings: AU Passata if the TTFs are shipped next to the document (fonts/), else the
% installed font of that name, else a sans-serif that is always there.
\IfFileExists{./fonts/AUPassata_Rg.ttf}{%
  \newfontfamily\headingfont[Path=./fonts/, Ligatures=TeX, UprightFont=AUPassata_Rg.ttf, BoldFont=AUPassata_Bold.ttf]{AUPassata}%
}{%
  \IfFontExistsTF{AU Passata}{\newfontfamily\headingfont[Ligatures=TeX]{AU Passata}}{\newfontfamily\headingfont[Ligatures=TeX]{Latin Modern Sans}}%
}
% Body: Libertinus Serif (system font or the libertinus-otf package's files), else Latin Modern.
\IfFontExistsTF{Libertinus Serif}{\setmainfont{Libertinus Serif}}{%
  \IfFontExistsTF{LibertinusSerif-Regular.otf}{%
    \setmainfont{LibertinusSerif-Regular.otf}[BoldFont=LibertinusSerif-Bold.otf,
      ItalicFont=LibertinusSerif-Italic.otf, BoldItalicFont=LibertinusSerif-BoldItalic.otf]%
  }{\setmainfont{Latin Modern Roman}}%
}
\IfFontExistsTF{Libertinus Mono}{\setmonofont{Libertinus Mono}[Scale=MatchLowercase]}{}

\linespread{1.02}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.55\baselineskip}

% ----- Headings -------------------------------------------------------------------
\titleformat{\section}{\headingfont\fontsize{14}{17}\selectfont\bfseries\color{aublue}}{\thesection}{0.6em}{}
\titlespacing*{\section}{0pt}{1.7\baselineskip}{0.3\baselineskip}
\titleformat{\subsection}{\headingfont\fontsize{11.5}{14}\selectfont\bfseries\color{aublue}}{\thesubsection}{0.6em}{}
\titlespacing*{\subsection}{0pt}{1.0\baselineskip}{0.2\baselineskip}
\titleformat{\subsubsection}{\headingfont\fontsize{10.5}{13}\selectfont\bfseries\color{aublue}}{\thesubsubsection}{0.6em}{}
\titlespacing*{\subsubsection}{0pt}{0.8\baselineskip}{0.15\baselineskip}

% ----- Header: section on the left, page number on the right, rule underneath ------
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.5pt}
\renewcommand{\sectionmark}[1]{\markright{\thesection\ #1}}
\fancyhead[L]{\headingfont\footnotesize\nouppercase{\rightmark}}
\fancyhead[R]{\headingfont\footnotesize\thepage}
\fancypagestyle{plain}{\fancyhf{}\renewcommand{\headrulewidth}{0pt}}

% ----- Captions, lists, tables -------------------------------------------------------
\captionsetup{font=small, labelfont=bf, skip=4pt}
\setlist{nosep, leftmargin=1.2em}
\setlist[itemize]{label=\textbullet}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\renewcommand{\arraystretch}{1.12}
% A grey section row spanning all columns of a booktabs table:
%   \sectionrow{3}{Data analysis — raw data → prepared data}
\newcommand{\sectionrow}[2]{\multicolumn{#1}{@{}>{\columncolor{black!8}}l@{}}{\textbf{#2}}\\}
\RequirePackage{colortbl}

% ----- Bibliography: author-year. APA if biblatex-apa is installed (it is on Overleaf), ------
% otherwise biblatex's built-in authoryear style. Cite with \parencite{key} -> (Author, 2020)
% and \textcite{key} -> Author (2020).
\IfFileExists{apa.bbx}{\PassOptionsToPackage{style=apa}{biblatex}}{\PassOptionsToPackage{style=authoryear, sorting=nyt}{biblatex}}
\RequirePackage[backend=biber, maxbibnames=6, minbibnames=5, giveninits=true, doi=true, url=true, isbn=false]{biblatex}
\renewcommand*{\bibfont}{\small}

\RequirePackage[hidelinks]{hyperref}

% ----- Cover -------------------------------------------------------------------------
\newcommand{\aur@category}{}
\newcommand{\aur@affiliation}{}
\newcommand{\aur@coverimage}{}
\newcommand{\aur@logo}{}
\newcommand{\category}[1]{\renewcommand{\aur@category}{#1}}
\newcommand{\affiliation}[1]{\renewcommand{\aur@affiliation}{#1}}
\newcommand{\coverimage}[1]{\renewcommand{\aur@coverimage}{#1}}
\newcommand{\logo}[1]{\renewcommand{\aur@logo}{#1}}
% Geometry of the cut, as in cover.typ: where the slanted edge meets the left/right page
% edge (measured from the top) and how far down the photo starts.
\newcommand{\aur@cutleft}{0.58}
\newcommand{\aur@cutright}{0.76}
\newcommand{\aur@imagetop}{0.44}
\newsavebox{\aur@imgbox}
\newlength{\aur@bandheight}

\newcommand{\makecover}{%
  \begin{titlepage}%
  \pagecolor{aublue}\color{white}\headingfont
  \begin{tikzpicture}[remember picture, overlay]
    % Photo along the bottom, scaled to cover the band and clipped ("fit: cover").
    \ifdefempty{\aur@coverimage}{}{%
      \setlength{\aur@bandheight}{\paperheight}\addtolength{\aur@bandheight}{-\aur@imagetop\paperheight}%
      \sbox{\aur@imgbox}{\includegraphics[height=\aur@bandheight]{\aur@coverimage}}%
      \ifdim\wd\aur@imgbox<\paperwidth
        \sbox{\aur@imgbox}{\includegraphics[width=\paperwidth]{\aur@coverimage}}%
      \fi
      \begin{scope}
        \clip (current page.south west) rectangle ([yshift=\aur@bandheight]current page.south east);
        \node[anchor=south, inner sep=0] at (current page.south) {\usebox{\aur@imgbox}};
      \end{scope}
      % Slanted blue field over the top of the photo.
      \fill[aublue] (current page.north west) -- (current page.north east)
        -- ([yshift=-\aur@cutright\paperheight]current page.north east)
        -- ([yshift=-\aur@cutleft\paperheight]current page.north west) -- cycle;
    }%
    % Logo, top right.
    \node[anchor=north east, inner sep=0] at ([xshift=-2.4cm, yshift=-2.2cm]current page.north east) {\aur@logo};
    % Text block on the 1.5 cm grid.
    \node[anchor=north west, inner sep=0, text width=14.2cm, align=left] at ([xshift=3.4cm, yshift=-6cm]current page.north west) {%
      {\fontsize{15}{18}\selectfont\aur@category\par}
      \vspace{0.9cm}
      {\fontsize{38}{46}\selectfont\raggedright\hyphenpenalty=10000\@title\par}
      \vspace{1.3cm}
      {\fontsize{14}{17}\selectfont\@date\par}
      \vspace{0.7cm}
      {\fontsize{12}{15}\selectfont\bfseries\def\and{\\[0.25cm]}\@author\par}
      \vspace{0.25cm}
      {\fontsize{12}{15}\selectfont\aur@affiliation\par}
    };
  \end{tikzpicture}%
  \end{titlepage}%
  \nopagecolor\color{black}%
  \setcounter{page}{1}%
}

% ----- Appendices: lettered sections, figures/tables numbered A1, A2, … --------------
\let\aur@appendix\appendix
\renewcommand{\appendix}{%
  \clearpage
  \aur@appendix
  \setcounter{figure}{0}\renewcommand{\thefigure}{A\arabic{figure}}%
  \setcounter{table}{0}\renewcommand{\thetable}{A\arabic{table}}%
  \begin{center}{\headingfont\fontsize{16}{19}\selectfont\bfseries\color{aublue}Appendices}\end{center}%
}
\endinput
