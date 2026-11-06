import { Component, HostBinding, ChangeDetectionStrategy } from '@angular/core';
import { ToastService } from './toast.service';
import { NgbToast } from '@ng-bootstrap/ng-bootstrap';



@Component({
  standalone: true,
	selector: 'shpp-toasts',
	template: `
		@for (toast of toastService.toasts; track toast) {
		  <ngb-toast
		    [class]="toast.className"
		    [autohide]="true"
		    [delay]="toast.delay || 5000"
		    (hidden)="toastService.remove(toast)"
		    >
		    {{ toast.text }}
		  </ngb-toast>
		}
		`,
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [NgbToast]
})
export class ToastsContainerComponent {
  @HostBinding('class') classAttr = 'toast-container position-fixed top-0 end-0 p-3';
  @HostBinding('style') styleAttr = 'z-index: 1200';

	constructor(public toastService: ToastService) {}
}
