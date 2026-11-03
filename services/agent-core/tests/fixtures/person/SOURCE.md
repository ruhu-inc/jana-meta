# Person-gate fixture

`arial-44-worksheet.png`: an owned, rendered worksheet with no person in it (LicenseRef-Own): 1400x1000 white page, black
Arial 44 text in three lines at x=100, y=110/200/290, Pillow 12.3.0 on macOS. It is committed as pixels because Linux has
no Arial. The retired Haar/HOG stack refused it on both platforms (HOG box weight 0.47).

No photo of a real person is committed here. `test_person_gate.drawn_face` paints a face in code; it shows the pinned
detector is alive and refuses through the real worker, and says nothing about how many real people are caught. That
evidence is `evals/perception/person`.
