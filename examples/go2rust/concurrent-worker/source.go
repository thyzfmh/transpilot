// Go 源代码: 并发 Worker Pool 模式
package worker

import (
	"context"
	"fmt"
	"sync"
)

type Job struct {
	ID   int
	Data string
}

type Result struct {
	JobID  int
	Output string
	Err    error
}

func ProcessJobs(ctx context.Context, jobs []Job, workerCount int) []Result {
	jobCh := make(chan Job, len(jobs))
	resultCh := make(chan Result, len(jobs))

	var wg sync.WaitGroup

	// 启动 workers
	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for job := range jobCh {
				select {
				case <-ctx.Done():
					resultCh <- Result{JobID: job.ID, Err: ctx.Err()}
					return
				default:
					output := fmt.Sprintf("worker-%d processed: %s", id, job.Data)
					resultCh <- Result{JobID: job.ID, Output: output}
				}
			}
		}(i)
	}

	// 发送 jobs
	for _, job := range jobs {
		jobCh <- job
	}
	close(jobCh)

	// 等待完成
	go func() {
		wg.Wait()
		close(resultCh)
	}()

	// 收集结果
	var results []Result
	for r := range resultCh {
		results = append(results, r)
	}
	return results
}
